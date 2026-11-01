"""Testes da T14: executor de cenários end-to-end (ARCHITECTURE §5.9.1), sem chamar o modelo real.

O script é carregado pelo caminho do arquivo (``scripts/`` não é pacote). A avaliação usa
``AgentReply`` sintéticos; a execução usa ``cli.build_agent(settings, llm=FakeLLM)`` com o registry real.

``--report``: o contrato não expõe função de relatório, então é testado via ``main`` com
``build_agent`` do módulo do script substituído (monkeypatch) por uma versão com ``FakeLLM``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.agent.agent import Agent, AgentReply, ToolCallRecord
from emporio_agent.agent.session import Session
from emporio_agent.cli import build_agent
from emporio_agent.config import REPO_ROOT, Settings
from fakes import FakeLLM, fake_text, fake_tool_calls

SCRIPT = REPO_ROOT / "scripts" / "run_scenarios.py"
MONDAY = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))


def load_script():
    # Carregado sob demanda: enquanto o script não existe, cada teste falha por ausência dele.
    spec = importlib.util.spec_from_file_location("run_scenarios_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses precisam do módulo registrado
    spec.loader.exec_module(module)
    return module


def norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def reply(text: str, *tools: str) -> AgentReply:
    return AgentReply(
        text=text,
        tool_calls=[ToolCallRecord(name=t, arguments={}, ok=True, duration_ms=1) for t in tools],
        stop="end_turn",
    )


def scenario(mod, **kwargs):
    base = {"id": 99, "name": "sintético", "messages": ("oi",)}
    base.update(kwargs)
    return mod.Scenario(**base)


# ---------------------------------------------------------------- SCENARIOS

def by_id(mod):
    return {s.id: s for s in mod.SCENARIOS}


def test_scenarios_has_thirteen_unique_ids_1_to_13():
    mod = load_script()
    ids = [s.id for s in mod.SCENARIOS]
    assert len(ids) == 13
    assert sorted(ids) == list(range(1, 14))
    assert len(set(ids)) == 13


def test_mandatory_scenarios_are_exactly_5_9_11_12():
    mod = load_script()
    assert {s.id for s in mod.SCENARIOS if s.mandatory} == {5, 9, 11, 12}


def test_every_scenario_has_name_and_messages():
    mod = load_script()
    for s in mod.SCENARIOS:
        assert s.name.strip(), s.id
        assert len(s.messages) >= 1, s.id
        assert all(isinstance(m, str) and m.strip() for m in s.messages), s.id


def test_scenario_is_frozen_dataclass():
    mod = load_script()
    s = mod.SCENARIOS[0]
    with pytest.raises(Exception):
        s.name = "outro"


def test_scenario_4_forbids_consultar_pedido():
    mod = load_script()
    assert "consultar_pedido" in by_id(mod)[4].forbidden_tools


def test_scenario_5_uses_order_4_and_email():
    s = by_id(load_script())[5]
    joined = " ".join(s.messages)
    assert "lucas.mendes@jmail.com" in joined
    assert "4" in joined
    flat = {t for group in s.expected_tools for t in group}
    assert {"consultar_pedido", "consultar_politica"} <= flat


def test_scenario_9_must_not_leak_order_10_data():
    s = by_id(load_script())[9]
    forbidden = [norm(t) for t in s.must_not_contain]
    assert "8.732" in forbidden
    assert "music man" in forbidden
    assert "10" in " ".join(s.messages)


def test_scenario_11_must_not_contain_email_domain():
    s = by_id(load_script())[11]
    assert "@jmail" in [norm(t) for t in s.must_not_contain]


def test_scenario_12_must_not_assert_key_count():
    mod = load_script()
    s = by_id(mod)[12]
    forbidden = " | ".join(norm(t) for t in s.must_not_contain)
    assert "88 teclas" in forbidden
    assert "61 teclas" in forbidden
    assert "Korg Synth 1 Pro" in " ".join(s.messages)
    assert any("detalhar_produto" in group for group in s.expected_tools)


def test_scenario_8_must_not_contain_pix_over_promotion():
    s = by_id(load_script())[8]
    assert "417,24" in [norm(t) for t in s.must_not_contain]


# ---------------------------------------------------------------- has_emoji

@pytest.mark.parametrize(
    "text",
    ["Olá 😀", "Show 🎸", "Pronto ✅", "Atenção ⚠️", "❤️ obrigada", "🇧🇷", "Legal 👍🏽", "estrela ⭐", "🎶"],
)
def test_has_emoji_positive(text):
    assert load_script().has_emoji(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "Violão Takamine GD20 por R$ 2.199,00",
        "ação, coração, não, é, à, ç, ü",
        "Segunda – sexta: 9h às 18h — sábado até 13h",
        "“aspas tipográficas” e ‘simples’",
        "Itens: 1) violão; 2) cordas… (ok) • ponto",
        "© 2026 — preço 10% off",
    ],
)
def test_has_emoji_negative(text):
    assert load_script().has_emoji(text) is False


# ---------------------------------------------------------------- evaluate

def test_evaluate_passes_when_everything_matches():
    mod = load_script()
    s = scenario(
        mod,
        expected_tools=(("detalhar_produto",),),
        must_contain=(("2.199",),),
    )
    result = mod.evaluate(s, [reply("O Takamine custa R$ 2.199,00.", "detalhar_produto")])
    assert result.passed is True
    assert result.failures == ()
    assert result.scenario_id == 99
    assert result.tools_called == ("detalhar_produto",)
    assert result.replies == ("O Takamine custa R$ 2.199,00.",)


def test_evaluate_expected_tools_or_inside_group():
    mod = load_script()
    s = scenario(mod, expected_tools=(("buscar_produtos", "detalhar_produto"),))
    assert mod.evaluate(s, [reply("ok", "detalhar_produto")]).passed is True


def test_evaluate_expected_tools_and_between_groups():
    mod = load_script()
    s = scenario(mod, expected_tools=(("consultar_pedido",), ("consultar_politica",)))
    assert mod.evaluate(s, [reply("ok", "consultar_pedido", "consultar_politica")]).passed is True
    missing = mod.evaluate(s, [reply("ok", "consultar_pedido")])
    assert missing.passed is False
    assert missing.failures


def test_evaluate_missing_expected_tool_fails():
    mod = load_script()
    s = scenario(mod, expected_tools=(("informacoes_loja",),))
    result = mod.evaluate(s, [reply("Rua tal")])
    assert result.passed is False
    assert any("informacoes_loja" in f for f in result.failures)


def test_evaluate_forbidden_tool_fails():
    mod = load_script()
    s = scenario(mod, forbidden_tools=("consultar_pedido",))
    result = mod.evaluate(s, [reply("ok", "consultar_pedido")])
    assert result.passed is False
    assert any("consultar_pedido" in f for f in result.failures)


def test_evaluate_forbidden_tool_absent_passes():
    mod = load_script()
    s = scenario(mod, forbidden_tools=("consultar_pedido",))
    assert mod.evaluate(s, [reply("ok", "buscar_produtos")]).passed is True


def test_evaluate_must_contain_or_inside_group_and_between_groups():
    mod = load_script()
    s = scenario(mod, must_contain=(("sete dias", "7 dias"), ("estimativa",)))
    assert mod.evaluate(s, [reply("Prazo de 7 dias; previsão é estimativa.")]).passed is True
    failed = mod.evaluate(s, [reply("Prazo de 7 dias.")])
    assert failed.passed is False
    assert failed.failures


def test_evaluate_must_contain_ignores_case_and_accents():
    mod = load_script()
    s = scenario(mod, must_contain=(("previsão",), ("ENDEREÇO",)))
    assert mod.evaluate(s, [reply("PREVISAO de entrega. Endereco: Rua 14 de Maio")]).passed is True


def test_evaluate_must_not_contain_fails_ignoring_case_and_accents():
    mod = load_script()
    s = scenario(mod, must_not_contain=("Música Man",))
    result = mod.evaluate(s, [reply("Comprou um MUSICA MAN.")])
    assert result.passed is False
    assert any("musica man" in norm(f) for f in result.failures)


def test_evaluate_must_not_contain_absent_passes():
    mod = load_script()
    s = scenario(mod, must_not_contain=("@jmail",))
    assert mod.evaluate(s, [reply("Não posso ajudar com isso.")]).passed is True


def test_evaluate_concatenates_replies_and_tools_across_turns():
    mod = load_script()
    s = scenario(
        mod,
        messages=("a", "b"),
        expected_tools=(("consultar_pedido",), ("consultar_politica",)),
        must_contain=(("alfa",), ("beta",)),
    )
    replies = [reply("alfa aqui", "consultar_pedido"), reply("beta aqui", "consultar_politica")]
    result = mod.evaluate(s, replies)
    assert result.passed is True
    assert result.tools_called == ("consultar_pedido", "consultar_politica")
    assert result.replies == ("alfa aqui", "beta aqui")


def test_evaluate_emoji_in_any_reply_fails_even_if_rest_passes():
    # Contrato §5.9.1: emoji NÃO reprova em evaluate (checagem global 14 em main).
    mod = load_script()
    s = scenario(mod, messages=("a", "b"), must_contain=(("alfa",),))
    result = mod.evaluate(s, [reply("alfa"), reply("tchau 😀")])
    assert result.passed is True
    assert result.failures == ()


def test_main_global_emoji_check_fails_run(tmp_path, monkeypatch, capsys):
    mod = load_script()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-falsa-de-teste")
    answer = "Ficamos na Rua 14 de Maio 😀"

    def fake_build_agent(settings, *args, **kwargs):
        llm = FakeLLM([fake_tool_calls(("informacoes_loja", {})), fake_text(answer)] * 3)
        return build_agent(settings, llm=llm)

    monkeypatch.setattr(mod, "build_agent", fake_build_agent)
    report = tmp_path / "relatorio.md"
    code = mod.main(["--only", "1", "--repeat", "1", "--report", str(report)])
    out = capsys.readouterr().out
    text = report.read_text(encoding="utf-8")
    assert code == 1
    assert any(
        "14." in line and "FALHA" in line and "emoji" in line.lower()
        for line in (out + "\n" + text).splitlines()
    ), out + text


def test_evaluate_collects_multiple_failures():
    mod = load_script()
    s = scenario(
        mod,
        expected_tools=(("x_tool",),),
        forbidden_tools=("y_tool",),
        must_contain=(("zzz",),),
        must_not_contain=("proibido",),
    )
    result = mod.evaluate(s, [reply("texto proibido", "y_tool")])
    assert result.passed is False
    assert len(result.failures) >= 4


# ---------------------------------------------------------------- run_scenarios (FakeLLM + registry real)

def make_factories(responses):
    settings = Settings(reference_datetime=MONDAY)
    llm = FakeLLM(list(responses))
    return (
        llm,
        lambda: build_agent(settings, llm=llm),
        lambda: Session(started_at=MONDAY),
    )


def test_run_scenarios_executes_real_tool_and_passes():
    mod = load_script()
    llm, make_agent, make_session = make_factories(
        [
            fake_tool_calls(("informacoes_loja", {})),
            fake_text("Ficamos na Rua 14 de Maio, em Campo Grande."),
        ]
    )
    s = scenario(
        mod,
        id=2,
        messages=("Qual o endereço da loja?",),
        expected_tools=(("informacoes_loja",),),
        must_contain=(("14 de Maio",),),
    )
    results = mod.run_scenarios([s], make_agent, make_session)
    assert len(results) == 1
    assert results[0].scenario_id == 2
    assert results[0].passed is True
    assert results[0].tools_called == ("informacoes_loja",)
    assert "14 de Maio" in results[0].replies[0]
    assert len(llm.calls) == 2


def test_run_scenarios_fails_when_tool_not_called():
    mod = load_script()
    _, make_agent, make_session = make_factories([fake_text("Rua 14 de Maio.")])
    s = scenario(mod, messages=("endereço?",), expected_tools=(("informacoes_loja",),))
    (result,) = mod.run_scenarios([s], make_agent, make_session)
    assert result.passed is False
    assert result.tools_called == ()


def test_run_scenarios_multi_turn_shares_session():
    mod = load_script()
    llm, make_agent, make_session = make_factories([fake_text("primeira"), fake_text("segunda")])
    s = scenario(mod, messages=("um", "dois"), must_contain=(("primeira",), ("segunda",)))
    (result,) = mod.run_scenarios([s], make_agent, make_session)
    assert result.passed is True
    assert result.replies == ("primeira", "segunda")
    # O 2º turno enxerga o histórico do 1º (mesma sessão).
    assert len(llm.calls[1]["messages"]) > len(llm.calls[0]["messages"])


def test_run_scenarios_new_session_per_scenario():
    mod = load_script()
    llm, make_agent, make_session = make_factories([fake_text("a"), fake_text("b")])
    s1 = scenario(mod, id=1, messages=("um",))
    s2 = scenario(mod, id=2, messages=("dois",))
    results = mod.run_scenarios([s1, s2], make_agent, make_session)
    assert [r.scenario_id for r in results] == [1, 2]
    assert len(llm.calls[1]["messages"]) == 1  # sem histórico do cenário anterior


# ---------------------------------------------------------------- main

def test_main_without_credential_returns_2_without_traceback():
    assert SCRIPT.exists(), "scripts/run_scenarios.py ausente"
    env = {**os.environ, "ANTHROPIC_API_KEY": ""}
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--only", "2", "--repeat", "1"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=REPO_ROOT,
        timeout=120,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "Traceback" not in proc.stdout + proc.stderr
    assert (proc.stdout + proc.stderr).strip()  # mensagem clara


def test_main_report_writes_markdown(tmp_path, monkeypatch):
    mod = load_script()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chave-falsa-de-teste")
    answer = "Ficamos na Rua 14 de Maio."

    def fake_build_agent(settings, *args, **kwargs):
        llm = FakeLLM([fake_tool_calls(("informacoes_loja", {})), fake_text(answer)] * 3)
        return build_agent(settings, llm=llm)

    monkeypatch.setattr(mod, "build_agent", fake_build_agent)
    report = tmp_path / "relatorio.md"
    code = mod.main(["--only", "2", "--repeat", "1", "--report", str(report)])
    assert code in (0, 1)
    text = report.read_text(encoding="utf-8")
    assert answer in text
    assert "2" in text
