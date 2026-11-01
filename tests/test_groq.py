"""Testes da T08b: adaptador Groq (conversões, requisição, tool_use_failed, erros, factory, padrões).

Sem rede: as respostas são ``groq.types.chat.ChatCompletion`` reais e o cliente do SDK é um falso
que grava os kwargs de ``chat.completions.create``.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import groq
import httpx
import pytest
from groq.types import CompletionUsage
from groq.types.chat import ChatCompletion, ChatCompletionMessage, ChatCompletionMessageToolCall
from groq.types.chat.chat_completion import Choice
from groq.types.chat.chat_completion_message_tool_call import Function

from emporio_agent.config import Settings, load_settings, read_env
from emporio_agent.llm.anthropic_client import AnthropicClient
from emporio_agent.llm.base import LLMError, LLMResponse, Message, ToolCall, ToolSpec
from emporio_agent.llm.factory import create_llm_client
from emporio_agent.llm.groq_client import (
    GroqClient,
    from_groq_response,
    to_groq_messages,
    to_groq_tools,
)

SECRET = "gsk_segredo_123456"
GPT_OSS = "openai/gpt-oss-120b"
API_TEXT = "TEXTO-BRUTO-DA-API"


# --- helpers ------------------------------------------------------------------

def groq_tool_call(id_: str = "call_1", name: str = "buscar_produtos", arguments: str | None = '{"texto": "violão"}'):
    return {"id": id_, "type": "function", "function": {"name": name, "arguments": arguments}}


def completion(
    content: str | None = "oi",
    tool_calls: list[dict] | None = None,
    finish_reason: str = "stop",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> ChatCompletion:
    message: dict = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return ChatCompletion.model_validate({
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": GPT_OSS,
        "choices": [{"index": 0, "finish_reason": finish_reason, "message": message}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    })


def loose_completion(
    content: str | None = "oi",
    tool_calls: list[tuple[str, str, str | None]] | None = None,
    finish_reason: str = "stop",
) -> ChatCompletion:
    """Como o SDK real (sem validação estrita): admite valores fora do literal, ex. ``arguments=None``."""
    calls = None
    if tool_calls is not None:
        calls = [
            ChatCompletionMessageToolCall.model_construct(
                id=id_, type="function", function=Function.model_construct(name=name, arguments=args)
            )
            for id_, name, args in tool_calls
        ]
    message = ChatCompletionMessage.model_construct(role="assistant", content=content, tool_calls=calls)
    choice = Choice.model_construct(index=0, finish_reason=finish_reason, message=message)
    usage = CompletionUsage.model_construct(prompt_tokens=10, completion_tokens=5, total_tokens=15)
    return ChatCompletion.model_construct(
        id="chatcmpl-1", object="chat.completion", created=1, model=GPT_OSS, choices=[choice], usage=usage
    )


def sdk_request(status: int = 400) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))


def status_error(cls, status: int, body=None):
    return cls(f"falha {API_TEXT} chave {SECRET}", response=sdk_request(status), body=body)


def tool_use_failed_error() -> groq.BadRequestError:
    body = {"error": {"message": f"{API_TEXT} <function=x>", "type": "invalid_request_error", "code": "tool_use_failed"}}
    return status_error(groq.BadRequestError, 400, body)


class FakeGroq:
    """Cliente SDK falso: grava os kwargs e devolve/lança o roteirizado, na ordem."""

    def __init__(self, *script):
        self.script = list(script) if script else [completion()]
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        item = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def kwargs(self) -> dict:
        assert len(self.calls) == 1
        return self.calls[0]


def make_client(fake: FakeGroq, *, model: str = GPT_OSS, effort: str = "low", **extra) -> GroqClient:
    return GroqClient(model=model, effort=effort, api_key=SECRET, client=fake, **extra)


TOOLS = [ToolSpec(name="buscar_produtos", description="Busca", input_schema={"type": "object", "properties": {}})]


def complete(client: GroqClient, **overrides) -> LLMResponse:
    args = dict(
        system="ESTAVEL", system_dynamic="Agora: 2026-03-25", messages=[Message(role="user", content="olá")],
        tools=TOOLS, max_tokens=4096,
    )
    args.update(overrides)
    return client.complete(**args)


# --- to_groq_messages ---------------------------------------------------------

def test_two_system_messages_then_user():
    out = to_groq_messages("ESTAVEL", "DINAMICO", [Message(role="user", content="olá")])
    assert out == [
        {"role": "system", "content": "ESTAVEL"},
        {"role": "system", "content": "DINAMICO"},
        {"role": "user", "content": "olá"},
    ]


def test_single_system_when_no_dynamic():
    out = to_groq_messages("ESTAVEL", None, [Message(role="user", content="olá")])
    assert [m["role"] for m in out] == ["system", "user"]


def test_assistant_with_tool_calls_has_json_string_arguments():
    msg = Message(
        role="assistant", content="Vou buscar.",
        tool_calls=[ToolCall(id="c1", name="buscar_produtos", arguments={"texto": "violão", "n": 2})],
    )
    out = to_groq_messages("S", None, [msg])
    assistant = out[1]
    assert assistant["role"] == "assistant"
    assert assistant["content"] == "Vou buscar."
    (call,) = assistant["tool_calls"]
    assert call["id"] == "c1"
    assert call["type"] == "function"
    assert call["function"]["name"] == "buscar_produtos"
    assert isinstance(call["function"]["arguments"], str)
    assert json.loads(call["function"]["arguments"]) == {"texto": "violão", "n": 2}
    assert "violão" in call["function"]["arguments"]  # ensure_ascii=False


def test_assistant_tool_call_without_text_has_none_content():
    msg = Message(role="assistant", tool_calls=[ToolCall(id="c1", name="x", arguments={})])
    assistant = to_groq_messages("S", None, [msg])[1]
    assert assistant["content"] is None
    assert assistant["tool_calls"][0]["function"]["arguments"] == "{}"


def test_assistant_without_tool_calls_omits_key():
    out = to_groq_messages("S", None, [Message(role="assistant", content="Claro!")])
    assert out[1] == {"role": "assistant", "content": "Claro!"}
    assert "tool_calls" not in out[1]


def test_provider_content_is_ignored():
    msg = Message(role="assistant", content="ok", provider_content=[{"type": "thinking", "thinking": "x"}])
    out = to_groq_messages("S", None, [msg])
    assert out[1] == {"role": "assistant", "content": "ok"}


def test_tool_message():
    msgs = [Message(role="tool", tool_call_id="c1", content='{"ok": true}')]
    out = to_groq_messages("S", None, msgs)
    assert out[1] == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'}


def test_tool_error_message_keeps_same_shape():
    msgs = [Message(role="tool", tool_call_id="c1", content='{"ok": false}', is_error=True)]
    assert to_groq_messages("S", None, msgs)[1] == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": false}'}


def test_full_turn_order_preserved():
    msgs = [
        Message(role="user", content="oi"),
        Message(role="assistant", tool_calls=[ToolCall(id="a", name="x", arguments={}), ToolCall(id="b", name="y", arguments={})]),
        Message(role="tool", tool_call_id="a", content="1"),
        Message(role="tool", tool_call_id="b", content="2"),
    ]
    out = to_groq_messages("S", None, msgs)
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool", "tool"]


# --- to_groq_tools ------------------------------------------------------------

def test_to_groq_tools():
    schema = {"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]}
    out = to_groq_tools([ToolSpec(name="buscar_produtos", description="Busca", input_schema=schema)])
    assert out == [{
        "type": "function",
        "function": {"name": "buscar_produtos", "description": "Busca", "parameters": schema},
    }]


# --- from_groq_response -------------------------------------------------------

def test_response_text_only():
    out = from_groq_response(completion("Olá! Como posso ajudar?"))
    assert out.text == "Olá! Como posso ajudar?"
    assert out.tool_calls == []
    assert out.stop_reason == "end_turn"
    assert out.raw_stop_reason == "stop"
    assert out.provider_content is None


def test_response_empty_text_is_none():
    assert from_groq_response(completion("")).text is None
    assert from_groq_response(completion(None)).text is None


def test_response_tool_calls_parse_arguments():
    resp = completion(
        None,
        [groq_tool_call("c1", "buscar_produtos", '{"texto": "violão"}'), groq_tool_call("c2", "listar_categorias", "{}")],
        finish_reason="tool_calls",
    )
    out = from_groq_response(resp)
    assert out.stop_reason == "tool_use"
    assert out.text is None
    assert out.tool_calls == [
        ToolCall(id="c1", name="buscar_produtos", arguments={"texto": "violão"}),
        ToolCall(id="c2", name="listar_categorias", arguments={}),
    ]


@pytest.mark.parametrize("raw", ["{texto: sem aspas", "", "não é json", None])
def test_response_invalid_or_empty_arguments_become_empty_dict(raw):
    resp = loose_completion(None, [("c1", "x", raw)], finish_reason="tool_calls")
    out = from_groq_response(resp)
    assert out.tool_calls == [ToolCall(id="c1", name="x", arguments={})]


@pytest.mark.parametrize("raw,expected", [
    ("stop", "end_turn"),
    ("tool_calls", "tool_use"),
    ("length", "max_tokens"),
    ("content_filter", "refusal"),
    ("function_call", "other"),
    ("algo_novo", "other"),
])
def test_finish_reason_mapping(raw, expected):
    out = from_groq_response(loose_completion("x", finish_reason=raw))
    assert out.stop_reason == expected
    assert out.raw_stop_reason == raw


def test_usage_mapping():
    out = from_groq_response(completion(prompt_tokens=123, completion_tokens=45))
    assert out.usage == {"input_tokens": 123, "output_tokens": 45}


def test_roundtrip_response_to_message_to_groq_messages():
    resp = completion("Vou buscar.", [groq_tool_call("c1", "x", '{"a": 1}')], finish_reason="tool_calls")
    msg = from_groq_response(resp).to_message()
    out = to_groq_messages("S", None, [msg])
    assert json.loads(out[1]["tool_calls"][0]["function"]["arguments"]) == {"a": 1}


# --- requisição montada -------------------------------------------------------

def test_request_basic_shape():
    fake = FakeGroq()
    out = complete(make_client(fake, effort="medium"))
    kwargs = fake.kwargs
    assert kwargs["model"] == GPT_OSS
    assert kwargs["max_completion_tokens"] == 4096
    assert "max_tokens" not in kwargs
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["tools"] == to_groq_tools(TOOLS)
    assert kwargs["messages"] == to_groq_messages("ESTAVEL", "Agora: 2026-03-25", [Message(role="user", content="olá")])
    assert kwargs["reasoning_effort"] == "medium"
    assert kwargs["include_reasoning"] is False
    assert out.text == "oi"


def test_request_without_tools_omits_tools_and_tool_choice():
    fake = FakeGroq()
    complete(make_client(fake), tools=[])
    assert "tools" not in fake.kwargs
    assert "tool_choice" not in fake.kwargs


def test_request_has_no_sampling_params():
    fake = FakeGroq()
    complete(make_client(fake))
    for forbidden in ("temperature", "top_p", "top_k", "parallel_tool_calls"):
        assert forbidden not in fake.kwargs


@pytest.mark.parametrize("effort,expected", [
    ("low", "low"), ("medium", "medium"), ("high", "high"), ("xhigh", "high"), ("max", "high"),
])
def test_reasoning_effort_mapping_for_gpt_oss(effort, expected):
    fake = FakeGroq()
    complete(make_client(fake, effort=effort))
    assert fake.kwargs["reasoning_effort"] == expected


@pytest.mark.parametrize("model", ["openai/gpt-oss-20b", "openai/gpt-oss-120b"])
def test_gpt_oss_family_gets_reasoning_params(model):
    fake = FakeGroq()
    complete(make_client(fake, model=model))
    assert fake.kwargs["reasoning_effort"] == "low"
    assert fake.kwargs["include_reasoning"] is False


def test_other_models_omit_reasoning_params():
    fake = FakeGroq()
    complete(make_client(fake, model="llama-3.3-70b-versatile", effort="high"))
    kwargs = fake.kwargs
    assert kwargs["model"] == "llama-3.3-70b-versatile"
    assert "reasoning_effort" not in kwargs
    assert "include_reasoning" not in kwargs
    assert kwargs["tool_choice"] == "auto"


# --- tool_use_failed ----------------------------------------------------------

def test_tool_use_failed_is_retried_once_and_succeeds():
    fake = FakeGroq(tool_use_failed_error(), completion("ok depois"))
    out = complete(make_client(fake))
    assert len(fake.calls) == 2
    assert fake.calls[0] == fake.calls[1]
    assert out.text == "ok depois"


def test_tool_use_failed_twice_raises_bad_request():
    fake = FakeGroq(tool_use_failed_error(), tool_use_failed_error())
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake))
    assert exc.value.kind == "bad_request"
    assert len(fake.calls) == 2
    assert API_TEXT not in str(exc.value)
    assert SECRET not in str(exc.value)


def test_tool_use_failed_retries_zero_does_not_retry():
    fake = FakeGroq(tool_use_failed_error(), completion("nunca"))
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake, tool_use_failed_retries=0))
    assert exc.value.kind == "bad_request"
    assert len(fake.calls) == 1


def test_other_bad_request_is_not_retried():
    body = {"error": {"message": "x", "code": "invalid_request"}}
    fake = FakeGroq(status_error(groq.BadRequestError, 400, body), completion("nunca"))
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake))
    assert exc.value.kind == "bad_request"
    assert len(fake.calls) == 1


def test_bad_request_without_body_is_not_retried():
    fake = FakeGroq(status_error(groq.BadRequestError, 400, None), completion("nunca"))
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake))
    assert exc.value.kind == "bad_request"
    assert len(fake.calls) == 1


# --- paciência extra para 429 -------------------------------------------------

def rate_limit_error(retry_after: str | None) -> groq.RateLimitError:
    headers = {} if retry_after is None else {"retry-after": retry_after}
    response = httpx.Response(
        429, headers=headers, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )
    return groq.RateLimitError(f"falha {API_TEXT}", response=response, body=None)


def test_rate_limit_short_retry_after_waits_and_succeeds():
    sleeps: list[float] = []
    fake = FakeGroq(rate_limit_error("12"), completion("ok"))
    out = complete(make_client(fake, sleep=sleeps.append))
    assert out.text == "ok"
    assert sleeps == [12.0]
    assert len(fake.calls) == 2


def test_rate_limit_retries_at_most_three_times():
    sleeps: list[float] = []
    fake = FakeGroq(rate_limit_error("90"))
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake, sleep=sleeps.append))
    assert exc.value.kind == "rate_limit"
    assert sleeps == [90.0, 90.0, 90.0]
    assert len(fake.calls) == 4


@pytest.mark.parametrize("header", ["91", "600", None, "abc"])
def test_rate_limit_long_or_missing_retry_after_does_not_wait(header):
    sleeps: list[float] = []
    fake = FakeGroq(rate_limit_error(header), completion("nunca"))
    with pytest.raises(LLMError) as exc:
        complete(make_client(fake, sleep=sleeps.append))
    assert exc.value.kind == "rate_limit"
    assert sleeps == []
    assert len(fake.calls) == 1


# --- exceções do SDK ----------------------------------------------------------

@pytest.mark.parametrize("make_error,kind", [
    (lambda: status_error(groq.AuthenticationError, 401), "auth"),
    (lambda: status_error(groq.PermissionDeniedError, 403), "auth"),
    (lambda: status_error(groq.RateLimitError, 429), "rate_limit"),
    (lambda: groq.APIConnectionError(request=sdk_request().request), "connection"),
    (lambda: groq.APITimeoutError(request=sdk_request().request), "connection"),
    (lambda: status_error(groq.BadRequestError, 400), "bad_request"),
    (lambda: status_error(groq.InternalServerError, 500), "server"),
    (lambda: status_error(groq.NotFoundError, 404), "api"),
])
def test_sdk_exceptions_mapped_to_llm_error(make_error, kind):
    client = make_client(FakeGroq(make_error()))
    with pytest.raises(LLMError) as exc:
        complete(client)
    assert exc.value.kind == kind
    assert exc.value.message
    assert SECRET not in exc.value.message
    assert API_TEXT not in exc.value.message
    assert SECRET not in str(exc.value)
    assert API_TEXT not in str(exc.value)


def test_auth_error_mentions_groq_api_key_and_env():
    client = make_client(FakeGroq(status_error(groq.AuthenticationError, 401)))
    with pytest.raises(LLMError) as exc:
        complete(client)
    assert "GROQ_API_KEY" in exc.value.message
    assert ".env" in exc.value.message


# --- factory ------------------------------------------------------------------

def test_factory_groq_without_key_raises_auth_mentioning_env():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="groq"), env={})
    assert exc.value.kind == "auth"
    assert "GROQ_API_KEY" in exc.value.message
    assert ".env" in exc.value.message


def test_factory_groq_blank_key_raises_auth():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(), env={"GROQ_API_KEY": "  "})
    assert exc.value.kind == "auth"


def test_factory_default_settings_ignores_anthropic_key():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(), env={"ANTHROPIC_API_KEY": "sk-ant-x"})
    assert exc.value.kind == "auth"
    assert "GROQ_API_KEY" in exc.value.message


def test_factory_builds_groq_client_with_key():
    client = create_llm_client(Settings(), env={"GROQ_API_KEY": SECRET})
    assert isinstance(client, GroqClient)


def test_factory_anthropic_unchanged():
    client = create_llm_client(
        Settings(llm_provider="anthropic", llm_model="claude-sonnet-5-5"), env={"ANTHROPIC_API_KEY": "sk-ant-x"}
    )
    assert isinstance(client, AnthropicClient)


def test_factory_anthropic_without_key_still_auth():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="anthropic"), env={"GROQ_API_KEY": SECRET})
    assert exc.value.kind == "auth"
    assert "ANTHROPIC_API_KEY" in exc.value.message


def test_factory_unknown_provider_raises_config_naming_both():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="openai"), env={"GROQ_API_KEY": SECRET})
    assert exc.value.kind == "config"
    assert "anthropic" in exc.value.message
    assert "groq" in exc.value.message


# --- Settings padrão ----------------------------------------------------------

def test_settings_defaults_are_groq():
    s = Settings()
    assert s.llm_provider == "groq"
    assert s.llm_model == GPT_OSS
    assert s.llm_max_tokens == 4096
    assert s.llm_effort == "low"


def test_load_settings_defaults_without_env(tmp_path):
    s = load_settings(env_file=tmp_path / "nao_existe.env", environ={})
    assert (s.llm_provider, s.llm_model, s.llm_max_tokens) == ("groq", GPT_OSS, 4096)


# --- smoke test real (pulado por padrão: pytest -m llm) -----------------------

@pytest.mark.llm
def test_real_smoke_groq_responds_to_ola():
    env = read_env()
    if not (env.get("GROQ_API_KEY") or "").strip():
        pytest.skip("GROQ_API_KEY ausente no .env/ambiente")
    client = create_llm_client(load_settings(), env)
    response = client.complete(
        system="Você é um atendente de loja de instrumentos musicais. Responda em português, em uma frase curta.",
        system_dynamic=None,
        messages=[Message(role="user", content="olá")],
        tools=[],
        max_tokens=1024,
    )
    assert response.stop_reason == "end_turn"
    assert response.text and response.text.strip()
    assert response.usage.get("output_tokens", 0) > 0
