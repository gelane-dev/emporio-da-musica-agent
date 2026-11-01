"""Testes da T15: gravador de conversas de exemplo (ARCHITECTURE §5.9.2), sem chamar o modelo real.

O script é carregado pelo caminho do arquivo (``scripts/`` não é pacote). A gravação usa
``build_agent`` do módulo do script substituído (monkeypatch) por uma versão com ``FakeLLM``.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

from emporio_agent.cli import build_agent
from emporio_agent.config import REPO_ROOT
from emporio_agent.llm.base import LLMError
from fakes import FakeLLM, fake_text, fake_tool_calls

SCRIPT = REPO_ROOT / "scripts" / "record_example.py"
REFERENCE = "2026-03-25T10:00"
REAL_PHRASE = "Conversa real, transcrita sem edição por scripts/record_example.py."
TRANSCRIPT_TITLE = "# Conversa — Empório da Música"


def load_script():
    # Carregado sob demanda: enquanto o script não existe, cada teste falha por ausência dele.
    assert SCRIPT.exists(), "scripts/record_example.py ausente"
    spec = importlib.util.spec_from_file_location("record_example_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses precisam do módulo registrado
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _settings_env(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "chave-falsa-de-teste")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "modelo-de-teste/xyz-1")
    monkeypatch.setenv("LLM_EFFORT", "medium")


def install_llm(monkeypatch, mod, responses):
    llm = FakeLLM(responses)
    monkeypatch.setattr(mod, "build_agent", lambda settings, *a, **kw: build_agent(settings, llm=llm))
    return llm


def write_script(tmp_path, text):
    path = tmp_path / "roteiro.txt"
    path.write_text(text, encoding="utf-8")
    return path


def run(mod, script, out, *extra):
    return mod.main(["--script", str(script), "--out", str(out), "--pause", "0", *extra])


def header_of(path):
    return path.read_text(encoding="utf-8").split(TRANSCRIPT_TITLE)[0]


def test_script_ignores_comments_and_blank_lines(tmp_path, monkeypatch):
    mod = load_script()
    llm = install_llm(monkeypatch, mod, [fake_text("Resposta um."), fake_text("Resposta dois.")])
    script = write_script(
        tmp_path, "# comentário\n\nOi, tudo bem?\n   \n# outro comentário\nQuanto custa o ukulele?\n\n"
    )
    out = tmp_path / "saida.md"
    assert run(mod, script, out) == 0
    assert len(llm.calls) == 2  # uma chamada por fala; comentários e vazias não viram turnos
    text = out.read_text(encoding="utf-8")
    assert "**Cliente:** Oi, tudo bem?" in text
    assert "**Cliente:** Quanto custa o ukulele?" in text
    assert "comentário" not in text


def test_recording_writes_header_then_transcript(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(
        monkeypatch,
        mod,
        [
            fake_tool_calls(("informacoes_loja", {})),
            fake_text("Ficamos na Rua 14 de Maio."),
            fake_text("De nada!"),
        ],
    )
    script = write_script(tmp_path, "Onde fica a loja?\nObrigado\n")
    out = tmp_path / "saida.md"
    assert run(mod, script, out, "--title", "Teste de loja", "--reference-date", REFERENCE) == 0

    text = out.read_text(encoding="utf-8")
    header, sep, transcript = text.partition(TRANSCRIPT_TITLE)
    assert sep, "transcript ausente"
    assert header.startswith("# Exemplo — Teste de loja")
    assert REFERENCE in header or "25/03/2026" in header  # data de referência
    assert "groq" in header
    assert "modelo-de-teste/xyz-1" in header
    assert "medium" in header
    assert REAL_PHRASE in header
    assert "commit" in header.lower()
    # textos devolvidos pelo FakeLLM e linhas de ferramenta, exatamente como no transcript
    assert "**Mel:** Ficamos na Rua 14 de Maio." in transcript
    assert "**Mel:** De nada!" in transcript
    assert "> Ferramenta: `informacoes_loja` {} (ok)" in transcript


def test_header_title_defaults_to_script_name(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(monkeypatch, mod, [fake_text("Olá!")])
    script = tmp_path / "01_catalogo_violoes.txt"
    script.write_text("Oi\n", encoding="utf-8")
    out = tmp_path / "saida.md"
    assert run(mod, script, out) == 0
    assert out.read_text(encoding="utf-8").startswith("# Exemplo — ")
    assert "01_catalogo_violoes" in header_of(out)


def test_header_commit_unknown_when_git_fails(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(monkeypatch, mod, [fake_text("Olá!")])

    def boom(*args, **kwargs):
        raise OSError("git indisponível")

    monkeypatch.setattr(subprocess, "run", boom)
    script = write_script(tmp_path, "Oi\n")
    out = tmp_path / "saida.md"
    assert run(mod, script, out) == 0
    assert "desconhecido" in header_of(out)


def test_transcript_keeps_order_and_ends_with_last_reply(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(monkeypatch, mod, [fake_text("Primeira."), fake_text("Segunda.")])
    script = write_script(tmp_path, "um\ndois\n")
    out = tmp_path / "saida.md"
    assert run(mod, script, out) == 0
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    body = text[text.index(TRANSCRIPT_TITLE) :]
    assert body.index("**Cliente:** um") < body.index("**Mel:** Primeira.") < body.index("**Cliente:** dois")
    assert body.rstrip().endswith("**Mel:** Segunda.")


# ---------------------------------------------------------------- --pause

def _sleeps(monkeypatch, tmp_path, n_turns, pause):
    import time

    mod = load_script()
    sleeps: list[float] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))
    install_llm(monkeypatch, mod, [fake_text(f"R{i}") for i in range(n_turns)])
    script = write_script(tmp_path, "".join(f"fala {i}\n" for i in range(n_turns)))
    out = tmp_path / "saida.md"
    code = mod.main(["--script", str(script), "--out", str(out), "--pause", str(pause)])
    assert code == 0
    return sleeps


def test_pause_zero_never_sleeps(tmp_path, monkeypatch):
    assert _sleeps(monkeypatch, tmp_path, 3, 0) == []


def test_pause_sleeps_between_turns_never_after_last(tmp_path, monkeypatch):
    assert _sleeps(monkeypatch, tmp_path, 3, 7) == [7, 7]


def test_pause_not_called_for_single_turn(tmp_path, monkeypatch):
    assert _sleeps(monkeypatch, tmp_path, 1, 7) == []


# ---------------------------------------------------------------- erros

def test_llm_error_returns_3_and_writes_no_file(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(monkeypatch, mod, [fake_text("Primeira ok."), LLMError("rate_limit", "cota esgotada")])
    script = write_script(tmp_path, "um\ndois\ntres\n")
    out = tmp_path / "saida.md"
    assert run(mod, script, out) == 3
    assert not out.exists()  # nunca há transcrição parcial
    assert list(tmp_path.glob("*.md")) == []


def test_without_credential_returns_2_no_traceback_no_file(tmp_path):
    assert SCRIPT.exists(), "scripts/record_example.py ausente"
    script = write_script(tmp_path, "Oi\n")
    out = tmp_path / "saida.md"
    env = {
        **os.environ,
        "GROQ_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_AUTH_TOKEN": "",
        "LLM_PROVIDER": "groq",
    }
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--script", str(script), "--out", str(out), "--pause", "0"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=REPO_ROOT,
        timeout=120,
    )
    output = proc.stdout + proc.stderr
    assert proc.returncode == 2, output
    assert "Traceback" not in output
    assert output.strip()  # mensagem clara
    assert not out.exists()


# ---------------------------------------------------------------- --force

def test_existing_file_without_force_errors_and_stays_intact(tmp_path, monkeypatch):
    mod = load_script()
    llm = install_llm(monkeypatch, mod, [fake_text("Nova resposta.")])
    script = write_script(tmp_path, "Oi\n")
    out = tmp_path / "saida.md"
    out.write_text("CONTEÚDO ORIGINAL", encoding="utf-8")
    assert run(mod, script, out) != 0
    assert out.read_text(encoding="utf-8") == "CONTEÚDO ORIGINAL"
    assert len(llm.calls) == 0  # falha cedo, sem gastar tokens


def test_force_overwrites_existing_file(tmp_path, monkeypatch):
    mod = load_script()
    install_llm(monkeypatch, mod, [fake_text("Nova resposta.")])
    script = write_script(tmp_path, "Oi\n")
    out = tmp_path / "saida.md"
    out.write_text("CONTEÚDO ORIGINAL", encoding="utf-8")
    assert run(mod, script, out, "--force") == 0
    text = out.read_text(encoding="utf-8")
    assert "CONTEÚDO ORIGINAL" not in text
    assert "**Mel:** Nova resposta." in text
