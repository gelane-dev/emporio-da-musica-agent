"""Testes da T11 (parte Agent): loop LLM <-> ferramentas (ARCHITECTURE §5.7.2), com FakeLLM e registry real."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.agent import agent as agent_module
from emporio_agent.agent.agent import (
    FALLBACK_EMPTY,
    FALLBACK_LLM_ERROR,
    FALLBACK_MAX_ITERATIONS,
    FALLBACK_REFUSAL,
    Agent,
    AgentReply,
    ToolCallRecord,
)
from emporio_agent.agent.prompts import build_system_prompt
from emporio_agent.agent.session import Session
from emporio_agent.config import REPO_ROOT, Settings
from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.llm.base import LLMError, LLMResponse, ToolCall
from emporio_agent.policies.store import PolicyStore
from emporio_agent.tools import build_tool_registry
from fakes import FakeLLM, fake_text, fake_tool_calls

TZ = ZoneInfo("America/Campo_Grande")
SUNDAY = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)

EMAIL = "pedro.oliveira@jmail.com"
PHONE = "(67) 98432-1098"
PHONE_DIGITS = "67984321098"
MAX_ITER = 3


@pytest.fixture(scope="module")
def policies() -> PolicyStore:
    return PolicyStore.from_markdown(REPO_ROOT / "knowledge" / "policies.md")


@pytest.fixture
def registry(store_data, policies):
    return build_tool_registry(
        CatalogRepository(store_data), OrderRepository(store_data), policies, lambda: SUNDAY
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(max_tool_iterations=MAX_ITER, max_history_turns=50)


def make_agent(llm, registry, settings, now=SUNDAY) -> Agent:
    return Agent(llm, registry, settings, clock=lambda: now)


def new_session() -> Session:
    return Session(SUNDAY)


def response(**overrides) -> LLMResponse:
    base = dict(
        text=None,
        tool_calls=[],
        stop_reason="end_turn",
        raw_stop_reason="end_turn",
        usage={"input_tokens": 11, "output_tokens": 7},
        provider_content=None,
    )
    base.update(overrides)
    return LLMResponse(**base)


def tool_messages(messages):
    return [m for m in messages if m.role == "tool"]


# ----------------------------------------------------------------------------- resposta direta


def test_resposta_direta_uma_chamada(registry, settings):
    llm = FakeLLM([fake_text("Olá! Sou a Mel.")])
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "oi")

    assert isinstance(reply, AgentReply)
    assert reply.text == "Olá! Sou a Mel."
    assert reply.tool_calls == []
    assert reply.stop == "end_turn"
    assert len(llm.calls) == 1
    assert [m.role for m in session.messages] == ["user", "assistant"]
    assert session.messages[0].content == "oi"
    assert session.messages[1].content == "Olá! Sou a Mel."


def test_chamada_ao_llm_leva_tools_max_tokens_e_mensagem_do_usuario(registry, settings):
    llm = FakeLLM([fake_text("ok")])
    make_agent(llm, registry, settings).respond(new_session(), "quais categorias?")
    call = llm.calls[0]
    assert call["max_tokens"] == settings.llm_max_tokens
    assert [t.name for t in call["tools"]] == registry.names()
    assert [(m.role, m.content) for m in call["messages"]] == [("user", "quais categorias?")]


# ----------------------------------------------------------------------------- tool calls


def test_tool_call_executa_e_anexa_resultado(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(("listar_categorias", {}), ids=["toolu_A"]),
            fake_text("Temos várias categorias."),
        ]
    )
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "quais categorias?")

    assert reply.text == "Temos várias categorias."
    assert reply.stop == "end_turn"
    assert len(llm.calls) == 2
    assert len(reply.tool_calls) == 1
    rec = reply.tool_calls[0]
    assert isinstance(rec, ToolCallRecord)
    assert rec.name == "listar_categorias" and rec.arguments == {} and rec.ok is True
    assert isinstance(rec.duration_ms, int) and rec.duration_ms >= 0

    second = llm.calls[1]["messages"]
    assert [m.role for m in second] == ["user", "assistant", "tool"]
    assert second[1].tool_calls[0].id == "toolu_A"
    result = second[2]
    assert result.tool_call_id == "toolu_A"
    assert result.is_error is False
    payload = json.loads(result.content)
    assert payload["ok"] is True and isinstance(payload["dados"], list)
    assert [m.role for m in session.messages] == ["user", "assistant", "tool", "assistant"]


def test_tool_com_erro_marca_is_error_e_record_ok_false(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(("consultar_pedido", {"pedido_id": 19, "email": "errado@x.com"}), ids=["E1"]),
            fake_text("Não consegui verificar."),
        ]
    )
    reply = make_agent(llm, registry, settings).respond(new_session(), "meu pedido 19")
    result = tool_messages(llm.calls[1]["messages"])[0]
    assert result.tool_call_id == "E1" and result.is_error is True
    assert json.loads(result.content)["erro"]["codigo"] == "VERIFICATION_FAILED"
    assert reply.tool_calls[0].ok is False
    assert reply.tool_calls[0].arguments == {"pedido_id": 19, "email": "errado@x.com"}


def test_varias_tool_calls_na_mesma_resposta_em_ordem_e_agrupadas(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(
                ("listar_categorias", {}),
                ("consultar_politica", {"topico": "horarios"}),
                ("informacoes_loja", {}),
                ids=["c1", "c2", "c3"],
            ),
            fake_text("Pronto."),
        ]
    )
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "tudo")

    assert [r.name for r in reply.tool_calls] == ["listar_categorias", "consultar_politica", "informacoes_loja"]
    assert all(r.ok for r in reply.tool_calls)
    second = llm.calls[1]["messages"]
    assert [m.role for m in second] == ["user", "assistant", "tool", "tool", "tool"]
    assert [m.tool_call_id for m in tool_messages(second)] == ["c1", "c2", "c3"]
    assert len(llm.calls) == 2  # uma única rodada de LLM para as três


def test_resultados_correspondem_ao_id_certo(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(
                ("consultar_politica", {"topico": "horarios"}), ("listar_categorias", {}), ids=["x", "y"]
            ),
            fake_text("ok"),
        ]
    )
    make_agent(llm, registry, settings).respond(new_session(), "?")
    by_id = {m.tool_call_id: json.loads(m.content) for m in tool_messages(llm.calls[1]["messages"])}
    assert by_id["x"]["dados"]["topico"] == "horarios"
    assert isinstance(by_id["y"]["dados"], list)


def test_varias_rodadas_de_ferramentas(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(("listar_categorias", {}), ids=["r1"]),
            fake_tool_calls(("informacoes_loja", {}), ids=["r2"]),
            fake_text("fim"),
        ]
    )
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "?")
    assert reply.stop == "end_turn" and reply.text == "fim"
    assert [r.name for r in reply.tool_calls] == ["listar_categorias", "informacoes_loja"]
    assert len(llm.calls) == 3
    assert [m.role for m in llm.calls[2]["messages"]] == [
        "user", "assistant", "tool", "assistant", "tool",
    ]


def test_tool_inexistente_devolve_erro_ao_llm_sem_crash(registry, settings):
    llm = FakeLLM([fake_tool_calls(("ferramenta_fantasma", {"a": 1}), ids=["g1"]), fake_text("Desculpe.")])
    reply = make_agent(llm, registry, settings).respond(new_session(), "?")
    assert reply.text == "Desculpe."
    assert reply.stop == "end_turn"
    assert reply.tool_calls[0].name == "ferramenta_fantasma" and reply.tool_calls[0].ok is False
    result = tool_messages(llm.calls[1]["messages"])[0]
    assert result.tool_call_id == "g1" and result.is_error is True
    assert json.loads(result.content)["erro"]["codigo"] == "INVALID_ARGUMENT"


def test_argumentos_invalidos_devolvem_erro_ao_llm(registry, settings):
    llm = FakeLLM([fake_tool_calls(("consultar_politica", {"topico": "inexistente"}), ids=["i1"]), fake_text("ok")])
    reply = make_agent(llm, registry, settings).respond(new_session(), "?")
    assert reply.tool_calls[0].ok is False
    assert tool_messages(llm.calls[1]["messages"])[0].is_error is True


# ----------------------------------------------------------------------------- limite de iterações


def test_max_iterations_fallback_stop_e_warning(registry, settings, caplog):
    llm = FakeLLM([fake_tool_calls(("listar_categorias", {}), ids=[f"m{i}"]) for i in range(MAX_ITER + 3)])
    session = new_session()
    with caplog.at_level(logging.DEBUG):
        reply = make_agent(llm, registry, settings).respond(session, "loop infinito")

    assert reply.stop == "max_iterations"
    assert reply.text == FALLBACK_MAX_ITERATIONS
    assert len(reply.tool_calls) == MAX_ITER
    assert MAX_ITER <= len(llm.calls) <= MAX_ITER + 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "esperava um log WARNING ao atingir max_tool_iterations"


def test_max_iterations_registra_fallback_na_sessao_e_historico_continua_valido(registry, settings):
    llm = FakeLLM(
        [fake_tool_calls(("listar_categorias", {}), ids=[f"m{i}"]) for i in range(MAX_ITER + 3)]
        + [fake_text("de volta")]
    )
    agent = make_agent(llm, registry, settings)
    session = new_session()
    agent.respond(session, "loop")
    last = session.messages[-1]
    assert last.role == "assistant" and last.content == FALLBACK_MAX_ITERATIONS
    # toda tool call do histórico tem resultado
    ids_calls = [c.id for m in session.messages for c in m.tool_calls]
    ids_results = [m.tool_call_id for m in tool_messages(session.messages)]
    assert ids_calls == ids_results

    # nova chamada funciona e vê o histórico anterior
    nova = FakeLLM([fake_text("de volta")])
    reply = make_agent(nova, registry, settings).respond(session, "e agora?")
    assert reply.text == "de volta" and reply.stop == "end_turn"
    assert nova.calls[0]["messages"][0].content == "loop"


def test_fallbacks_em_portugues_sem_emoji_e_distintos():
    textos = [FALLBACK_MAX_ITERATIONS, FALLBACK_REFUSAL, FALLBACK_EMPTY, FALLBACK_LLM_ERROR]
    for t in textos:
        assert isinstance(t, str) and t.strip()
        assert all(ord(ch) < 0x2190 or ch in "—–…" for ch in t), f"possível emoji em {t!r}"
    assert len(set(textos)) == 4


# ----------------------------------------------------------------------------- LLMError


def test_llm_error_fallback_sem_vazar_mensagem_tecnica(registry, settings, caplog):
    erro = LLMError("rate_limit", "Limite de requisições excedido (detalhe técnico XYZ).")
    llm = FakeLLM([erro])
    session = new_session()
    with caplog.at_level(logging.DEBUG):
        reply = make_agent(llm, registry, settings).respond(session, "oi")

    assert reply.stop == "llm_error"
    assert reply.text == FALLBACK_LLM_ERROR
    assert "XYZ" not in reply.text and "rate_limit" not in reply.text
    assert reply.tool_calls == []
    assert "XYZ" in caplog.text  # mensagem técnica só no log
    assert [m.role for m in session.messages] == ["user", "assistant"]
    assert session.messages[-1].content == FALLBACK_LLM_ERROR


def test_llm_error_no_meio_do_laco_mantem_records_e_proxima_resposta_funciona(registry, settings):
    llm = FakeLLM(
        [
            fake_tool_calls(("listar_categorias", {}), ids=["z1"]),
            LLMError("connection", "queda de rede"),
            fake_text("voltei"),
        ]
    )
    agent = make_agent(llm, registry, settings)
    session = new_session()
    reply = agent.respond(session, "primeira")
    assert reply.stop == "llm_error" and reply.text == FALLBACK_LLM_ERROR
    assert [r.name for r in reply.tool_calls] == ["listar_categorias"]

    reply2 = agent.respond(session, "segunda")
    assert reply2.text == "voltei" and reply2.stop == "end_turn"
    roles = [m.role for m in session.messages]
    assert roles == ["user", "assistant", "tool", "assistant", "user", "assistant"]


# ----------------------------------------------------------------------------- refusal / max_tokens / vazio


def test_refusal_com_texto_devolve_texto_do_modelo(registry, settings):
    llm = FakeLLM([response(text="Não posso ajudar com isso.", stop_reason="refusal", raw_stop_reason="refusal")])
    reply = make_agent(llm, registry, settings).respond(new_session(), "?")
    assert reply.stop == "refusal"
    assert reply.text == "Não posso ajudar com isso."


@pytest.mark.parametrize("vazio", [None, "", "   "])
def test_refusal_vazia_usa_fallback_e_registra_na_sessao(registry, settings, vazio):
    llm = FakeLLM([response(text=vazio, stop_reason="refusal", raw_stop_reason="refusal")])
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "?")
    assert reply.stop == "refusal"
    assert reply.text == FALLBACK_REFUSAL
    assert session.messages[-1].role == "assistant"
    assert session.messages[-1].content == FALLBACK_REFUSAL


def test_max_tokens_devolve_texto_como_veio(registry, settings):
    llm = FakeLLM([response(text="Resposta cortada no mei", stop_reason="max_tokens", raw_stop_reason="max_tokens")])
    reply = make_agent(llm, registry, settings).respond(new_session(), "?")
    assert reply.stop == "max_tokens"
    assert reply.text == "Resposta cortada no mei"


@pytest.mark.parametrize("vazio", [None, ""])
def test_texto_vazio_em_end_turn_usa_fallback_empty(registry, settings, vazio):
    llm = FakeLLM([response(text=vazio)])
    session = new_session()
    reply = make_agent(llm, registry, settings).respond(session, "?")
    assert reply.text == FALLBACK_EMPTY
    assert reply.stop == "end_turn"
    assert session.messages[-1].content == FALLBACK_EMPTY


# ----------------------------------------------------------------------------- system / dynamic / histórico


def test_system_estavel_entre_chamadas_e_igual_ao_prompt_das_tools(registry, settings):
    llm = FakeLLM(
        [fake_tool_calls(("listar_categorias", {})), fake_tool_calls(("informacoes_loja", {})), fake_text("ok")]
    )
    make_agent(llm, registry, settings).respond(new_session(), "?")
    systems = {c["system"] for c in llm.calls}
    assert len(systems) == 1
    assert systems == {build_system_prompt(registry.names())}


def test_system_estavel_entre_respostas_mesmo_com_clock_diferente(registry, settings):
    llm = FakeLLM([fake_text("a"), fake_text("b")])
    session = new_session()
    make_agent(llm, registry, settings, now=SUNDAY).respond(session, "1")
    make_agent(llm, registry, settings, now=MONDAY).respond(session, "2")
    assert llm.calls[0]["system"] == llm.calls[1]["system"]
    assert llm.calls[0]["system_dynamic"] != llm.calls[1]["system_dynamic"]


def test_system_dynamic_reflete_o_clock(registry, settings):
    llm = FakeLLM([fake_text("a")])
    make_agent(llm, registry, settings, now=SUNDAY).respond(new_session(), "?")
    dyn = llm.calls[0]["system_dynamic"]
    assert "01/11/2026" in dyn and "15:47" in dyn
    assert "01/11/2026" not in llm.calls[0]["system"]


def test_system_dynamic_igual_em_todas_as_chamadas_de_um_respond(registry, settings):
    llm = FakeLLM([fake_tool_calls(("listar_categorias", {})), fake_text("ok")])
    ticks = iter([SUNDAY, MONDAY, MONDAY])  # clock consultado uma vez por respond
    agent = Agent(llm, registry, settings, clock=lambda: next(ticks))
    agent.respond(new_session(), "?")
    assert llm.calls[0]["system_dynamic"] == llm.calls[1]["system_dynamic"]
    assert "01/11/2026" in llm.calls[0]["system_dynamic"]


def test_clock_padrao_usa_config_now(registry):
    settings = Settings(reference_datetime=MONDAY, max_tool_iterations=MAX_ITER)
    llm = FakeLLM([fake_text("a")])
    Agent(llm, registry, settings).respond(new_session(), "?")
    assert "02/11/2026" in llm.calls[0]["system_dynamic"]


def test_provider_content_preservado_no_historico_e_reenviado(registry, settings):
    bloco_pensamento = {"type": "thinking", "thinking": "hmm", "signature": "abc"}
    bloco_tool = {"type": "tool_use", "id": "p1", "name": "listar_categorias", "input": {}}
    r1 = response(
        tool_calls=[ToolCall(id="p1", name="listar_categorias", arguments={})],
        stop_reason="tool_use",
        raw_stop_reason="tool_use",
        provider_content=[bloco_pensamento, bloco_tool],
    )
    bloco_texto = {"type": "text", "text": "ok"}
    r2 = response(text="ok", provider_content=[{"type": "thinking", "thinking": "2", "signature": "s2"}, bloco_texto])
    llm = FakeLLM([r1, r2])
    session = new_session()
    make_agent(llm, registry, settings).respond(session, "?")

    assistentes = [m for m in session.messages if m.role == "assistant"]
    assert assistentes[0].provider_content == [bloco_pensamento, bloco_tool]
    assert assistentes[1].provider_content == r2.provider_content
    enviado = next(m for m in llm.calls[1]["messages"] if m.role == "assistant")
    assert enviado.provider_content == [bloco_pensamento, bloco_tool]
    assert enviado.tool_calls[0].id == "p1"


def test_historico_append_only_entre_respostas(registry, settings):
    llm = FakeLLM([fake_tool_calls(("listar_categorias", {}), ids=["h1"]), fake_text("um"), fake_text("dois")])
    agent = make_agent(llm, registry, settings)
    session = new_session()
    agent.respond(session, "primeira")
    snapshot = [m.model_dump() for m in session.messages]
    agent.respond(session, "segunda")
    assert [m.model_dump() for m in session.messages[: len(snapshot)]] == snapshot
    assert [m.role for m in llm.calls[2]["messages"]] == ["user", "assistant", "tool", "assistant", "user"]


def test_historico_enviado_respeita_max_history_turns(registry):
    settings = Settings(max_tool_iterations=MAX_ITER, max_history_turns=2)
    llm = FakeLLM([fake_text(f"r{i}") for i in range(1, 6)])
    agent = make_agent(llm, registry, settings)
    session = new_session()
    for i in range(1, 6):
        agent.respond(session, f"p{i}")
    enviado = llm.calls[-1]["messages"]
    assert [m.content for m in enviado] == ["p4", "r4", "p5"]
    assert len(session.messages) == 10  # sessão guarda tudo


def test_janela_enviada_nao_separa_tool_call_do_resultado(registry):
    settings = Settings(max_tool_iterations=MAX_ITER, max_history_turns=1)
    llm = FakeLLM(
        [
            fake_tool_calls(("listar_categorias", {}), ("informacoes_loja", {}), ids=["w1", "w2"]),
            fake_text("a"),
            fake_tool_calls(("listar_categorias", {}), ids=["w3"]),
            fake_text("b"),
        ]
    )
    agent = make_agent(llm, registry, settings)
    session = new_session()
    agent.respond(session, "p1")
    agent.respond(session, "p2")
    ultima = llm.calls[3]["messages"]
    assert [m.role for m in ultima] == ["user", "assistant", "tool"]
    assert ultima[0].content == "p2"


# ----------------------------------------------------------------------------- privacidade nos logs


def _todos_os_logs(caplog) -> str:
    partes = []
    for r in caplog.records:
        partes.append(r.getMessage())
        partes.append(str(r.args))
        if r.exc_text:
            partes.append(r.exc_text)
    partes.append(caplog.text)
    return "\n".join(partes)


@pytest.mark.parametrize(
    "args",
    [
        {"pedido_id": 19, "email": EMAIL},
        {"pedido_id": 19, "telefone": PHONE},
        {"pedido_id": 19, "email": "errado@x.com", "telefone": PHONE},
    ],
)
def test_logs_nao_contem_email_nem_telefone_do_consultar_pedido(registry, settings, caplog, args):
    llm = FakeLLM([fake_tool_calls(("consultar_pedido", args), ids=["lg"]), fake_text("ok")])
    with caplog.at_level(logging.DEBUG):
        make_agent(llm, registry, settings).respond(new_session(), "meu pedido")
    texto = _todos_os_logs(caplog)
    assert caplog.records, "o agente deveria registrar logs INFO"
    for segredo in (EMAIL, "errado@x.com", PHONE, PHONE_DIGITS, "98432-1098", "98432"):
        assert segredo not in texto


def test_logs_info_nao_contem_dados_do_resumo_de_encaminhar_atendente(
    store_data, policies, settings, caplog, tmp_path
):
    registry_h = build_tool_registry(
        CatalogRepository(store_data),
        OrderRepository(store_data),
        policies,
        lambda: SUNDAY,
        runtime_dir=tmp_path,
    )
    resumo = "Cliente lucas.mendes@jmail.com, telefone (67) 99812-3456, quer falar com humano."
    llm = FakeLLM(
        [
            fake_tool_calls(("encaminhar_atendente", {"motivo": "reclamacao", "resumo": resumo}), ids=["h1"]),
            fake_text("ok"),
        ]
    )
    with caplog.at_level(logging.INFO):
        make_agent(llm, registry_h, settings).respond(new_session(), "quero um atendente")
    texto = _todos_os_logs(caplog)
    assert caplog.records, "o agente deveria registrar logs INFO"
    assert "encaminhar_atendente" in texto
    for segredo in ("lucas.mendes@jmail.com", "99812-3456", "998123456", "99812"):
        assert segredo not in texto


def test_logs_info_registram_nome_da_tool(registry, settings, caplog):
    llm = FakeLLM([fake_tool_calls(("listar_categorias", {}), ids=["l1"]), fake_text("ok")])
    with caplog.at_level(logging.INFO):
        make_agent(llm, registry, settings).respond(new_session(), "?")
    assert "listar_categorias" in caplog.text


def test_logs_nao_contem_email_quando_tool_levanta_ou_falha(registry, settings, caplog):
    llm = FakeLLM([fake_tool_calls(("consultar_pedido", {"pedido_id": 99999, "email": EMAIL}), ids=["lg"]), fake_text("ok")])
    with caplog.at_level(logging.DEBUG):
        make_agent(llm, registry, settings).respond(new_session(), "meu pedido")
    assert EMAIL not in _todos_os_logs(caplog)


def test_modulo_expoe_constantes_do_contrato():
    for nome in ("FALLBACK_MAX_ITERATIONS", "FALLBACK_REFUSAL", "FALLBACK_EMPTY", "FALLBACK_LLM_ERROR"):
        assert hasattr(agent_module, nome)
