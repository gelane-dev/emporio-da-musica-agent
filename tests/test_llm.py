"""Testes da T08: adaptador LLM (conversões, requisição, erros, factory, config, FakeLLM)."""

from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx2
import pytest
from anthropic.types import Message as SdkMessage
from anthropic.types import TextBlock, ThinkingBlock, ToolUseBlock, Usage

from emporio_agent.config import Settings, load_settings, read_env
from emporio_agent.llm.anthropic_client import (
    AnthropicClient,
    from_anthropic_response,
    to_anthropic_messages,
)
from emporio_agent.llm.base import LLMError, LLMResponse, Message, ToolCall, ToolSpec
from emporio_agent.llm.factory import create_llm_client
from fakes import FakeLLM, fake_text, fake_tool_calls

SECRET = "sk-ant-segredo-123456"
BETA = "server-side-fallback-2026-07-01"


# --- helpers ------------------------------------------------------------------

def sdk_message(content, stop_reason="end_turn", **usage) -> SdkMessage:
    return SdkMessage(
        id="msg_1",
        type="message",
        role="assistant",
        model="claude-sonnet-5-5",
        content=content,
        stop_reason=stop_reason,
        stop_sequence=None,
        usage=Usage(input_tokens=usage.pop("input_tokens", 10), output_tokens=usage.pop("output_tokens", 5), **usage),
    )


def text_block(text: str) -> TextBlock:
    return TextBlock(type="text", text=text)


def tool_block(id_: str = "toolu_1", name: str = "buscar_produtos", input_: dict | None = None) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=id_, name=name, input=input_ or {"texto": "violão"})


def thinking_block() -> ThinkingBlock:
    return ThinkingBlock(type="thinking", thinking="pensando…", signature="sig-abc")


class FakeSdk:
    """Cliente SDK falso: grava os kwargs e devolve/lança o que foi roteirizado."""

    def __init__(self, result=None, error: Exception | None = None):
        self.result = result if result is not None else sdk_message([text_block("oi")])
        self.error = error
        self.calls: list[tuple[str, dict]] = []
        self.messages = SimpleNamespace(create=self._make("messages"))
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._make("beta")))

    def _make(self, path: str):
        def create(**kwargs):
            self.calls.append((path, kwargs))
            if self.error is not None:
                raise self.error
            return self.result

        return create

    @property
    def path(self) -> str:
        assert len(self.calls) == 1
        return self.calls[0][0]

    @property
    def kwargs(self) -> dict:
        assert len(self.calls) == 1
        return self.calls[0][1]


def make_client(fake: FakeSdk, *, effort="low", fallback=True) -> AnthropicClient:
    return AnthropicClient(model="claude-sonnet-5-5", effort=effort, refusal_fallback=fallback, client=fake)


TOOLS = [ToolSpec(name="buscar_produtos", description="Busca", input_schema={"type": "object", "properties": {}})]


def complete(client: AnthropicClient, **overrides) -> LLMResponse:
    args = dict(
        system="ESTAVEL", system_dynamic="Agora: 2026-03-25", messages=[Message(role="user", content="olá")],
        tools=TOOLS, max_tokens=16000,
    )
    args.update(overrides)
    return client.complete(**args)


def sdk_request(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))


# --- to_anthropic_messages ----------------------------------------------------

def test_user_message():
    assert to_anthropic_messages([Message(role="user", content="olá")]) == [{"role": "user", "content": "olá"}]


def test_assistant_text_only():
    out = to_anthropic_messages([Message(role="assistant", content="Claro!")])
    assert out == [{"role": "assistant", "content": [{"type": "text", "text": "Claro!"}]}]


def test_assistant_text_and_tool_use_without_provider_content():
    msg = Message(
        role="assistant", content="Vou buscar.",
        tool_calls=[ToolCall(id="t1", name="buscar_produtos", arguments={"texto": "violão"})],
    )
    (out,) = to_anthropic_messages([msg])
    assert out["role"] == "assistant"
    assert out["content"] == [
        {"type": "text", "text": "Vou buscar."},
        {"type": "tool_use", "id": "t1", "name": "buscar_produtos", "input": {"texto": "violão"}},
    ]


def test_assistant_tool_use_without_text_has_no_text_block():
    msg = Message(role="assistant", tool_calls=[ToolCall(id="t1", name="x", arguments={})])
    (out,) = to_anthropic_messages([msg])
    assert [b["type"] for b in out["content"]] == ["tool_use"]


def test_provider_content_resent_intact():
    raw = [
        {"type": "thinking", "thinking": "hmm", "signature": "sig-abc"},
        {"type": "text", "text": "ok"},
        {"type": "tool_use", "id": "t1", "name": "x", "input": {"a": 1}},
    ]
    msg = Message(
        role="assistant", content="ignorado", provider_content=raw,
        tool_calls=[ToolCall(id="t1", name="x", arguments={"a": 1})],
    )
    (out,) = to_anthropic_messages([msg])
    assert out["content"] == raw


def test_consecutive_tool_messages_grouped_in_single_user():
    msgs = [
        Message(role="user", content="oi"),
        Message(role="assistant", tool_calls=[ToolCall(id="a", name="x", arguments={}), ToolCall(id="b", name="y", arguments={})]),
        Message(role="tool", tool_call_id="a", content='{"ok":true}'),
        Message(role="tool", tool_call_id="b", content='{"ok":false}', is_error=True),
        Message(role="assistant", content="pronto"),
    ]
    out = to_anthropic_messages(msgs)
    assert [m["role"] for m in out] == ["user", "assistant", "user", "assistant"]
    results = out[2]["content"]
    assert [r["type"] for r in results] == ["tool_result", "tool_result"]
    assert [r["tool_use_id"] for r in results] == ["a", "b"]
    assert [r["content"] for r in results] == ['{"ok":true}', '{"ok":false}']
    assert [r["is_error"] for r in results] == [False, True]


def test_tool_messages_separated_by_other_message_are_not_merged():
    msgs = [
        Message(role="tool", tool_call_id="a", content="1"),
        Message(role="assistant", content="meio"),
        Message(role="tool", tool_call_id="b", content="2"),
    ]
    out = to_anthropic_messages(msgs)
    assert [m["role"] for m in out] == ["user", "assistant", "user"]
    assert len(out[0]["content"]) == len(out[2]["content"]) == 1


def test_conversion_does_not_mutate_input():
    raw = [{"type": "text", "text": "ok"}]
    msg = Message(role="assistant", provider_content=raw)
    to_anthropic_messages([msg])
    assert msg.provider_content == [{"type": "text", "text": "ok"}]


# --- from_anthropic_response --------------------------------------------------

def test_response_text_tool_use_and_thinking():
    resp = sdk_message(
        [thinking_block(), text_block("Vou buscar."), text_block("Um momento."), tool_block("toolu_9", "buscar_produtos", {"texto": "violão", "limite": 3})],
        stop_reason="tool_use",
    )
    out = from_anthropic_response(resp)
    assert isinstance(out, LLMResponse)
    assert out.text == "Vou buscar.\nUm momento."
    assert out.tool_calls == [ToolCall(id="toolu_9", name="buscar_produtos", arguments={"texto": "violão", "limite": 3})]
    assert isinstance(out.tool_calls[0].arguments, dict)
    assert out.stop_reason == "tool_use"
    assert out.raw_stop_reason == "tool_use"


def test_response_provider_content_complete_and_raw():
    blocks = [thinking_block(), text_block("oi"), tool_block()]
    out = from_anthropic_response(sdk_message(blocks, stop_reason="tool_use"))
    assert out.provider_content == [b.model_dump(mode="json", exclude_none=True) for b in blocks]
    assert [b["type"] for b in out.provider_content] == ["thinking", "text", "tool_use"]
    assert out.provider_content[0]["signature"] == "sig-abc"


def test_response_without_text_has_none():
    out = from_anthropic_response(sdk_message([tool_block()], stop_reason="tool_use"))
    assert out.text is None


def test_response_thinking_only_is_not_text():
    out = from_anthropic_response(sdk_message([thinking_block()], stop_reason="max_tokens"))
    assert out.text is None
    assert out.tool_calls == []
    assert len(out.provider_content) == 1


@pytest.mark.parametrize("sdk_reason,expected", [
    ("end_turn", "end_turn"),
    ("tool_use", "tool_use"),
    ("max_tokens", "max_tokens"),
    ("refusal", "refusal"),
    ("pause_turn", "other"),
    ("stop_sequence", "other"),
])
def test_stop_reason_mapping(sdk_reason, expected):
    out = from_anthropic_response(sdk_message([text_block("x")], stop_reason=sdk_reason))
    assert out.stop_reason == expected
    assert out.raw_stop_reason == sdk_reason


def test_usage_reported():
    out = from_anthropic_response(
        sdk_message([text_block("x")], input_tokens=100, output_tokens=20, cache_read_input_tokens=64, cache_creation_input_tokens=0)
    )
    assert out.usage["input_tokens"] == 100
    assert out.usage["output_tokens"] == 20
    assert out.usage["cache_read_input_tokens"] == 64


def test_to_message_roundtrip_preserves_provider_content():
    out = from_anthropic_response(sdk_message([thinking_block(), text_block("oi"), tool_block("t1")], stop_reason="tool_use"))
    msg = out.to_message()
    assert msg.role == "assistant"
    assert msg.content == "oi"
    assert msg.tool_calls == out.tool_calls
    assert msg.provider_content == out.provider_content
    (converted,) = to_anthropic_messages([msg])
    assert converted["content"] == out.provider_content


# --- requisição montada -------------------------------------------------------

FORBIDDEN = ("temperature", "top_p", "top_k", "tool_choice", "thinking")


def test_request_basic_shape_beta_path():
    fake = FakeSdk()
    complete(make_client(fake, effort="medium"))
    kwargs = fake.kwargs
    assert kwargs["model"] == "claude-sonnet-5-5"
    assert kwargs["max_tokens"] == 16000
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["messages"] == [{"role": "user", "content": "olá"}]
    assert kwargs["tools"] == [{"name": "buscar_produtos", "description": "Busca", "input_schema": {"type": "object", "properties": {}}}]


@pytest.mark.parametrize("fallback", [True, False])
def test_request_has_no_forbidden_params(fallback):
    fake = FakeSdk()
    complete(make_client(fake, fallback=fallback))
    extra = fake.kwargs.get("extra_body") or {}
    for name in FORBIDDEN:
        assert name not in fake.kwargs
        assert name not in extra


def test_system_cache_control_only_on_first_block():
    fake = FakeSdk()
    complete(make_client(fake))
    system = fake.kwargs["system"]
    assert system == [
        {"type": "text", "text": "ESTAVEL", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Agora: 2026-03-25"},
    ]


def test_system_without_dynamic_part_has_single_block():
    fake = FakeSdk()
    complete(make_client(fake), system_dynamic=None)
    system = fake.kwargs["system"]
    assert len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral"}


def test_refusal_fallback_true_uses_beta_with_fallbacks():
    fake = FakeSdk()
    complete(make_client(fake, fallback=True))
    assert fake.path == "beta"
    kwargs = fake.kwargs
    assert kwargs["betas"] == [BETA]
    fallbacks = kwargs.get("fallbacks", (kwargs.get("extra_body") or {}).get("fallbacks"))
    assert fallbacks == "default"


def test_refusal_fallback_false_uses_plain_messages_create():
    fake = FakeSdk()
    complete(make_client(fake, fallback=False))
    assert fake.path == "messages"
    kwargs = fake.kwargs
    assert "betas" not in kwargs
    assert "fallbacks" not in kwargs
    assert "fallbacks" not in (kwargs.get("extra_body") or {})
    assert kwargs["output_config"] == {"effort": "low"}


def test_complete_returns_converted_response():
    fake = FakeSdk(result=sdk_message([text_block("Olá!")]))
    out = complete(make_client(fake))
    assert out.text == "Olá!"
    assert out.stop_reason == "end_turn"


def test_complete_sends_tool_results_grouped():
    fake = FakeSdk()
    msgs = [
        Message(role="user", content="oi"),
        Message(role="assistant", tool_calls=[ToolCall(id="a", name="x", arguments={}), ToolCall(id="b", name="x", arguments={})]),
        Message(role="tool", tool_call_id="a", content="1"),
        Message(role="tool", tool_call_id="b", content="2"),
    ]
    complete(make_client(fake), messages=msgs)
    sent = fake.kwargs["messages"]
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert len(sent[2]["content"]) == 2


# --- exceções do SDK ----------------------------------------------------------

def _status_error(cls, status):
    return cls(f"falha com chave {SECRET}", response=sdk_request(status), body=None)


@pytest.mark.parametrize("make_error,kind", [
    (lambda: _status_error(anthropic.AuthenticationError, 401), "auth"),
    (lambda: _status_error(anthropic.PermissionDeniedError, 403), "auth"),
    (lambda: _status_error(anthropic.RateLimitError, 429), "rate_limit"),
    (lambda: anthropic.APIConnectionError(request=sdk_request(500).request), "connection"),
    (lambda: anthropic.APITimeoutError(request=sdk_request(500).request), "connection"),
    (lambda: _status_error(anthropic.BadRequestError, 400), "bad_request"),
    (lambda: _status_error(anthropic.InternalServerError, 500), "server"),
    (lambda: _status_error(anthropic.InternalServerError, 529), "server"),
    (lambda: _status_error(anthropic.NotFoundError, 404), "api"),
    (lambda: anthropic.APIError(f"erro {SECRET}", request=sdk_request(500).request, body=None), "api"),
])
@pytest.mark.parametrize("fallback", [True, False])
def test_sdk_exceptions_mapped_to_llm_error(make_error, kind, fallback):
    client = AnthropicClient(
        model="claude-sonnet-5-5", effort="low", refusal_fallback=fallback,
        api_key=SECRET, client=FakeSdk(error=make_error()),
    )
    with pytest.raises(LLMError) as exc:
        complete(client)
    assert exc.value.kind == kind
    assert exc.value.message
    assert SECRET not in exc.value.message
    assert SECRET not in str(exc.value)


# --- factory ------------------------------------------------------------------

def test_factory_without_key_raises_auth_mentioning_env():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="anthropic"), env={})
    assert exc.value.kind == "auth"
    assert ".env" in exc.value.message


def test_factory_blank_key_raises_auth():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="anthropic"), env={"ANTHROPIC_API_KEY": "  "})
    assert exc.value.kind == "auth"


def test_factory_unknown_provider_raises_config():
    with pytest.raises(LLMError) as exc:
        create_llm_client(Settings(llm_provider="openai"), env={"ANTHROPIC_API_KEY": SECRET})
    assert exc.value.kind == "config"
    assert "anthropic" in exc.value.message


def test_factory_builds_anthropic_client():
    client = create_llm_client(Settings(llm_provider="anthropic"), env={"ANTHROPIC_API_KEY": SECRET})
    assert isinstance(client, AnthropicClient)


# --- Settings / read_env ------------------------------------------------------

def test_settings_new_defaults():
    s = Settings()
    assert s.llm_effort == "low"
    assert s.llm_refusal_fallback is True
    assert s.llm_max_tokens == 4096


def test_load_settings_defaults_without_env(tmp_path):
    s = load_settings(env_file=tmp_path / "nao_existe.env", environ={})
    assert (s.llm_effort, s.llm_refusal_fallback, s.llm_max_tokens) == ("low", True, 4096)


def test_load_settings_reads_effort_and_max_tokens(tmp_path):
    s = load_settings(env_file=tmp_path / "x.env", environ={"LLM_EFFORT": "high", "LLM_MAX_TOKENS": "4096"})
    assert s.llm_effort == "high"
    assert s.llm_max_tokens == 4096


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("False", False), ("0", False), ("true", True), ("1", True), ("TRUE", True),
])
def test_load_settings_refusal_fallback_parse(tmp_path, raw, expected):
    s = load_settings(env_file=tmp_path / "x.env", environ={"LLM_REFUSAL_FALLBACK": raw})
    assert s.llm_refusal_fallback is expected


def test_load_settings_env_file_and_precedence(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_EFFORT=medium\nLLM_REFUSAL_FALLBACK=false\n", encoding="utf-8")
    s = load_settings(env_file=env_file, environ={"LLM_EFFORT": "max"})
    assert s.llm_effort == "max"
    assert s.llm_refusal_fallback is False


def test_invalid_effort_rejected(tmp_path):
    with pytest.raises(ValueError):
        load_settings(env_file=tmp_path / "x.env", environ={"LLM_EFFORT": "ultra"})


def test_read_env_merges_file_and_environ(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=do-arquivo\nOUTRA=1\n", encoding="utf-8")
    values = read_env(env_file=env_file, environ={"ANTHROPIC_API_KEY": "do-ambiente"})
    assert values["ANTHROPIC_API_KEY"] == "do-ambiente"
    assert values["OUTRA"] == "1"


def test_read_env_missing_file(tmp_path):
    assert read_env(env_file=tmp_path / "nao_existe.env", environ={"A": "b"}) == {"A": "b"}


# --- FakeLLM ------------------------------------------------------------------

def call_fake(llm: FakeLLM, messages=None) -> LLMResponse:
    return llm.complete(
        system="S", system_dynamic=None, messages=messages or [Message(role="user", content="oi")],
        tools=[], max_tokens=100,
    )


def test_fake_llm_returns_sequence_in_order():
    first, second = fake_text("um"), fake_text("dois")
    llm = FakeLLM([first, second])
    assert call_fake(llm) is first
    assert call_fake(llm) is second


def test_fake_llm_raises_scripted_exception():
    llm = FakeLLM([LLMError("rate_limit", "calma"), fake_text("ok")])
    with pytest.raises(LLMError) as exc:
        call_fake(llm)
    assert exc.value.kind == "rate_limit"
    assert call_fake(llm).text == "ok"


def test_fake_llm_exhausted_raises_assertion_error():
    llm = FakeLLM([fake_text("só um")])
    call_fake(llm)
    with pytest.raises(AssertionError):
        call_fake(llm)


def test_fake_llm_records_calls_with_deepcopied_messages():
    llm = FakeLLM([fake_text("a"), fake_text("b")])
    messages = [Message(role="user", content="oi")]
    call_fake(llm, messages)
    messages.append(Message(role="assistant", content="a"))
    call_fake(llm, messages)
    assert len(llm.calls) == 2
    assert llm.calls[0]["system"] == "S"
    assert llm.calls[0]["max_tokens"] == 100
    assert len(llm.calls[0]["messages"]) == 1  # cópia, não alterada depois
    assert len(llm.calls[1]["messages"]) == 2


def test_fake_text_helper():
    r = fake_text("olá")
    assert r.text == "olá"
    assert r.tool_calls == []
    assert r.stop_reason == "end_turn"


def test_fake_tool_calls_helper():
    r = fake_tool_calls(("buscar_produtos", {"texto": "x"}), ("listar_categorias", {}))
    assert r.stop_reason == "tool_use"
    assert [c.name for c in r.tool_calls] == ["buscar_produtos", "listar_categorias"]
    assert r.tool_calls[0].arguments == {"texto": "x"}
    assert len({c.id for c in r.tool_calls}) == 2


def test_fake_tool_calls_explicit_ids():
    r = fake_tool_calls(("a", {}), ("b", {}), ids=["id1", "id2"])
    assert [c.id for c in r.tool_calls] == ["id1", "id2"]


def test_fake_response_to_message():
    msg = fake_tool_calls(("a", {"k": 1})).to_message()
    assert msg.role == "assistant"
    assert msg.tool_calls[0].arguments == {"k": 1}


# --- smoke test real (pulado por padrão: pytest -m llm) -----------------------

@pytest.mark.llm
def test_real_smoke_responds_to_ola():
    env = read_env()
    if not (env.get("ANTHROPIC_API_KEY") or "").strip():
        pytest.skip("ANTHROPIC_API_KEY ausente no .env/ambiente")
    client = create_llm_client(load_settings().model_copy(update={"llm_provider": "anthropic", "llm_model": "claude-sonnet-5-5"}), env)
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
