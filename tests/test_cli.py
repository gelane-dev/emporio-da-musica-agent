"""Testes da T13: CLI (ARCHITECTURE §5.8.1), com FakeLLM, input roteirizado e console em memória."""

from __future__ import annotations

import io
import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from rich.console import Console

from emporio_agent.agent.agent import Agent
from emporio_agent.agent.session import Session
from emporio_agent.config import REPO_ROOT, Settings
from emporio_agent.domain.store_hours import store_status
from emporio_agent.llm.base import LLMError
from fakes import FakeLLM, fake_text, fake_tool_calls

TZ = ZoneInfo("America/Campo_Grande")
SUNDAY = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)  # loja fechada (domingo)
MONDAY = datetime(2026, 11, 2, 10, 0, tzinfo=TZ)  # loja aberta

# Pedido #4 pertence ao cliente 1 (Lucas Mendes da Silva).
EMAIL = "lucas.mendes@jmail.com"
PHONE = "(67) 99812-3456"
PHONE_DIGITS = "67998123456"

TRANSCRIPT_NAME = re.compile(r"^conversa-\d{8}-\d{6}-[0-9A-Za-z]+\.md$")
EMOJI = re.compile(
    "[\U0001f000-\U0001faff☀-➿⭐⭕⌚⌛⏩-⏺️‍]"
)


def import_cli():
    # Importado sob demanda: enquanto cli.py não existe, cada teste falha com ImportError.
    from emporio_agent import cli

    return cli


class Script:
    """``input_fn`` roteirizado; ao acabar o roteiro levanta ``exc`` (padrão EOFError)."""

    def __init__(self, *lines: str, exc: BaseException | None = None) -> None:
        self._lines = list(lines)
        self._exc = exc if exc is not None else EOFError()
        self.prompts: list[str] = []

    def __call__(self, prompt: str = "") -> str:
        self.prompts.append(prompt)
        if self._lines:
            return self._lines.pop(0)
        raise self._exc


def make_settings(tmp_path, now=MONDAY) -> Settings:
    return Settings(runtime_dir=tmp_path, reference_datetime=now)


def run(tmp_path, lines, responses=(), argv=(), now=MONDAY, exc=None):
    cli = import_cli()
    out = io.StringIO()
    console = Console(file=out, width=120, color_system=None, force_terminal=False)
    llm = FakeLLM(list(responses))
    code = cli.main(
        list(argv),
        settings=make_settings(tmp_path, now),
        llm=llm,
        input_fn=Script(*lines, exc=exc),
        console=console,
    )
    return code, out.getvalue(), llm


def transcripts(tmp_path):
    folder = tmp_path / "transcripts"
    return sorted(folder.glob("*.md")) if folder.is_dir() else []


# ----------------------------------------------------------------------------- saudação


def test_saudacao_loja_aberta(tmp_path):
    code, out, _ = run(tmp_path, [], now=MONDAY)
    assert code == 0
    assert "Mel" in out
    assert "Empório da Música" in out
    assert "09:00 às 18:00" in out or "aberta" in out.lower()
    # Aberta: não anuncia próxima abertura.
    assert "próxima abertura" not in out.lower()


def test_saudacao_loja_fechada_informa_proxima_abertura(tmp_path):
    code, out, _ = run(tmp_path, [], now=SUNDAY)
    assert code == 0
    assert "Mel" in out
    nxt = store_status(SUNDAY).next_opening
    assert nxt is not None and nxt.day == 2  # segunda, 02/11, 09:00
    assert "fechad" in out.lower()
    assert "segunda" in out.lower()
    assert "02/11" in out
    assert "09:00" in out


def test_greeting_funcao_sem_llm_e_sem_emoji():
    cli = import_cli()
    open_text = cli.greeting(MONDAY, store_status(MONDAY))
    closed_text = cli.greeting(SUNDAY, store_status(SUNDAY))
    assert "Mel" in open_text and "Mel" in closed_text
    assert "segunda" in closed_text.lower() and "02/11" in closed_text and "09:00" in closed_text
    assert "segunda" not in open_text.lower()
    assert not EMOJI.search(open_text + closed_text)


# ----------------------------------------------------------------------------- laço de conversa


def test_linha_vazia_ignorada_e_resposta_exibida(tmp_path):
    code, out, llm = run(
        tmp_path,
        ["", "   ", "Qual o endereço?"],
        [fake_text("Ficamos na Rua 14 de Maio, em Campo Grande.")],
    )
    assert code == 0
    assert len(llm.calls) == 1  # linhas vazias não chamam o modelo
    assert llm.calls[0]["messages"][-1].content == "Qual o endereço?"
    assert "Mel:" in out
    assert "14 de Maio" in out


def test_prompt_de_entrada_e_voce(tmp_path):
    cli = import_cli()
    script = Script("oi")
    console = Console(file=io.StringIO(), width=120, color_system=None)
    cli.main([], settings=make_settings(tmp_path), llm=FakeLLM([fake_text("Olá!")]), input_fn=script, console=console)
    assert script.prompts and all(p == "Você: " for p in script.prompts)


def test_varias_mensagens_mantem_historico(tmp_path):
    _, out, llm = run(tmp_path, ["oi", "tchau"], [fake_text("Olá!"), fake_text("Até logo!")])
    assert len(llm.calls) == 2
    assert [m.role for m in llm.calls[1]["messages"]] == ["user", "assistant", "user"]
    assert "Olá!" in out and "Até logo!" in out


def test_erro_do_llm_nao_gera_traceback(tmp_path):
    code, out, _ = run(tmp_path, ["oi"], [LLMError("api", "falha simulada")])
    assert code == 0
    assert "Traceback" not in out


# ----------------------------------------------------------------------------- --debug


def pedido_responses():
    return [
        fake_tool_calls(
            ("consultar_pedido", {"pedido_id": 4, "email": EMAIL, "telefone": PHONE}), ids=["t1"]
        ),
        fake_text("Seu pedido 4 foi entregue."),
    ]


def test_debug_mostra_nome_status_e_duracao_sem_dados_pessoais(tmp_path):
    code, out, _ = run(tmp_path, ["pedido 4"], pedido_responses(), argv=["--debug"])
    assert code == 0
    assert "consultar_pedido" in out
    assert re.search(r"\bok\b", out)
    assert re.search(r"\d+(\.\d+)?\s*(ms|s)\b", out)  # duração
    assert "pedido_id" in out and "4" in out
    assert "end_turn" in out  # stop do agente
    for secret in (EMAIL, PHONE, PHONE_DIGITS, "99812-3456", "99812"):
        assert secret not in out


def test_debug_mostra_erro_de_ferramenta(tmp_path):
    responses = [
        fake_tool_calls(("consultar_pedido", {"pedido_id": 4, "email": "errado@x.com"}), ids=["t1"]),
        fake_text("Não consegui confirmar."),
    ]
    _, out, _ = run(tmp_path, ["pedido 4"], responses, argv=["--debug"])
    assert "consultar_pedido" in out
    assert "erro" in out.lower()
    assert "errado@x.com" not in out


def test_sem_debug_nao_mostra_ferramentas(tmp_path):
    _, out, _ = run(tmp_path, ["pedido 4"], pedido_responses())
    assert "consultar_pedido" not in out
    assert "Seu pedido 4 foi entregue." in out


def test_debug_exibe_argumentos_de_outras_ferramentas(tmp_path):
    responses = [
        fake_tool_calls(("buscar_produtos", {"consulta": "violão"}), ids=["t1"]),
        fake_text("Encontrei opções."),
    ]
    _, out, _ = run(tmp_path, ["violão"], responses, argv=["--debug"])
    assert "buscar_produtos" in out
    assert "violão" in out


# ----------------------------------------------------------------------------- /salvar e --save


def test_comando_salvar_grava_transcript_e_mostra_caminho(tmp_path):
    code, out, _ = run(
        tmp_path,
        ["Qual o endereço?", "/salvar", "/sair"],
        [fake_text("Rua 14 de Maio.")],
    )
    assert code == 0
    files = transcripts(tmp_path)
    assert len(files) == 1
    assert TRANSCRIPT_NAME.match(files[0].name), files[0].name
    assert files[0].parent == tmp_path / "transcripts"
    text = files[0].read_text(encoding="utf-8")
    assert "**Cliente:** Qual o endereço?" in text
    assert "**Mel:** Rua 14 de Maio." in text
    assert files[0].name in out  # caminho informado


def test_nome_do_transcript_traz_data_hora_e_id_da_sessao(tmp_path):
    run(tmp_path, ["oi", "/salvar"], [fake_text("Olá!")], now=MONDAY)
    (path,) = transcripts(tmp_path)
    assert path.name.startswith("conversa-")
    stamp = re.match(r"conversa-(\d{8})-(\d{6})-", path.name)
    assert stamp is not None
    # O cabeçalho do transcript traz o mesmo id da sessão presente no nome do arquivo.
    session_id = path.stem.rsplit("-", 1)[1]
    assert f"Sessão: {session_id}" in path.read_text(encoding="utf-8")


def test_salvar_inclui_ferramentas_no_transcript(tmp_path):
    run(tmp_path, ["pedido 4", "/salvar"], pedido_responses())
    (path,) = transcripts(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "`consultar_pedido`" in text
    assert "Seu pedido 4 foi entregue." in text


def test_sem_save_nada_e_gravado_ao_encerrar(tmp_path):
    run(tmp_path, ["oi", "/sair"], [fake_text("Olá!")])
    assert transcripts(tmp_path) == []


def test_flag_save_grava_ao_encerrar_com_sair(tmp_path):
    code, out, _ = run(tmp_path, ["oi", "/sair"], [fake_text("Olá!")], argv=["--save"])
    assert code == 0
    (path,) = transcripts(tmp_path)
    assert TRANSCRIPT_NAME.match(path.name)
    assert "**Cliente:** oi" in path.read_text(encoding="utf-8")


def test_flag_save_grava_ao_encerrar_com_eof(tmp_path):
    code, _, _ = run(tmp_path, ["oi"], [fake_text("Olá!")], argv=["--save"])
    assert code == 0
    assert len(transcripts(tmp_path)) == 1


def test_flag_save_grava_ao_encerrar_com_ctrl_c(tmp_path):
    code, _, _ = run(tmp_path, ["oi"], [fake_text("Olá!")], argv=["--save"], exc=KeyboardInterrupt())
    assert code == 0
    assert len(transcripts(tmp_path)) == 1


# ----------------------------------------------------------------------------- /nova e /ajuda


def test_nova_reinicia_sessao_e_saúda_novamente(tmp_path):
    code, out, llm = run(
        tmp_path,
        ["meu nome é Ana", "/nova", "qual meu nome?"],
        [fake_text("Prazer, Ana!"), fake_text("Não sei o seu nome.")],
    )
    assert code == 0
    assert len(llm.calls) == 2
    # Segunda conversa começa do zero: só a nova mensagem do usuário.
    assert [m.content for m in llm.calls[1]["messages"]] == ["qual meu nome?"]
    assert out.count("Mel") >= 3  # saudação inicial + nova saudação + rótulos "Mel:"
    assert out.count("Empório da Música") >= 2


def test_nova_gera_transcript_apenas_da_sessao_nova(tmp_path):
    run(
        tmp_path,
        ["primeira conversa", "/nova", "segunda conversa", "/salvar"],
        [fake_text("a"), fake_text("b")],
    )
    (path,) = transcripts(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "segunda conversa" in text
    assert "primeira conversa" not in text


def test_ajuda_lista_comandos(tmp_path):
    code, out, llm = run(tmp_path, ["/ajuda"])
    assert code == 0
    for command in ("/sair", "/salvar", "/nova", "/ajuda"):
        assert command in out
    assert llm.calls == []  # comandos não vão ao modelo


def test_comandos_nao_chamam_o_modelo(tmp_path):
    _, _, llm = run(tmp_path, ["/ajuda", "/nova", "/salvar", "/sair"])
    assert llm.calls == []


# ----------------------------------------------------------------------------- encerramento


def test_sair_encerra_com_zero_e_despedida(tmp_path):
    cli = import_cli()
    script = Script("/sair", "nunca lida")
    out = io.StringIO()
    code = cli.main(
        [],
        settings=make_settings(tmp_path),
        llm=FakeLLM([]),
        input_fn=script,
        console=Console(file=out, width=120, color_system=None),
    )
    assert code == 0
    assert len(script.prompts) == 1  # não leu a segunda linha
    assert "Traceback" not in out.getvalue()


def test_eof_encerra_com_zero_sem_traceback(tmp_path):
    code, out, _ = run(tmp_path, [], exc=EOFError())
    assert code == 0
    assert "Traceback" not in out


def test_ctrl_c_encerra_com_zero_sem_traceback(tmp_path):
    code, out, _ = run(tmp_path, [], exc=KeyboardInterrupt())
    assert code == 0
    assert "Traceback" not in out


def test_ctrl_c_apos_conversa_encerra_com_zero(tmp_path):
    code, out, _ = run(tmp_path, ["oi"], [fake_text("Olá!")], exc=KeyboardInterrupt())
    assert code == 0
    assert "Olá!" in out
    assert "Traceback" not in out


# ----------------------------------------------------------------------------- build_agent


def test_build_agent_monta_oito_ferramentas(tmp_path):
    cli = import_cli()
    llm = FakeLLM([fake_text("ok")])
    agent = cli.build_agent(make_settings(tmp_path), llm=llm)
    assert isinstance(agent, Agent)
    agent.respond(Session(MONDAY), "oi")
    names = [spec.name for spec in llm.calls[0]["tools"]]
    assert sorted(names) == sorted(
        [
            "buscar_produtos",
            "detalhar_produto",
            "listar_categorias",
            "consultar_pedido",
            "consultar_politica",
            "informacoes_loja",
            "estimar_frete",
            "encaminhar_atendente",
        ]
    )
    assert len(names) == 8


def test_build_agent_usa_dados_reais(tmp_path):
    cli = import_cli()
    llm = FakeLLM(
        [fake_tool_calls(("consultar_pedido", {"pedido_id": 4, "email": EMAIL}), ids=["t1"]), fake_text("ok")]
    )
    agent = cli.build_agent(make_settings(tmp_path), llm=llm)
    reply = agent.respond(Session(MONDAY), "pedido 4")
    assert [(c.name, c.ok) for c in reply.tool_calls] == [("consultar_pedido", True)]


def test_build_agent_sem_chave_levanta_llm_error(tmp_path):
    cli = import_cli()
    with pytest.raises(LLMError) as info:
        cli.build_agent(make_settings(tmp_path), env={})
    assert info.value.kind == "auth"


# ----------------------------------------------------------------------------- erro de inicialização


def test_main_sem_credencial_retorna_2_sem_traceback(tmp_path, monkeypatch):
    cli = import_cli()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    out = io.StringIO()
    err = io.StringIO()
    console = Console(file=out, width=120, color_system=None)
    script = Script()
    code = cli.main([], settings=make_settings(tmp_path), input_fn=script, console=console)
    assert code == 2
    assert script.prompts == []  # nem chegou a ler entrada
    assert "Traceback" not in out.getvalue() + err.getvalue()


def test_subprocesso_sem_chave_codigo_2_cita_env_sem_traceback(tmp_path):
    env = os.environ.copy()
    env["ANTHROPIC_API_KEY"] = ""
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("LLM_PROVIDER", None)
    env.pop("ANTHROPIC_AUTH_TOKEN", None)
    proc = subprocess.run(
        [sys.executable, "-m", "emporio_agent"],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        cwd=tmp_path,
        timeout=60,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2, combined
    assert ".env" in combined
    assert "Traceback" not in combined


# ----------------------------------------------------------------------------- sem emojis


def test_saida_sem_emojis(tmp_path):
    responses = pedido_responses() + [fake_text("Posso ajudar em mais algo?")]
    _, out, _ = run(
        tmp_path,
        ["pedido 4", "/ajuda", "/nova", "/salvar", "oi"],
        responses,
        argv=["--debug"],
        now=SUNDAY,
    )
    assert out.strip()
    assert not EMOJI.search(out), [c for c in out if EMOJI.match(c)]


def test_emoji_regex_detecta_emojis_comuns():
    # Guarda do próprio teste: a regex precisa pegar os emojis mais usados.
    for ch in ("\U0001f60a", "\U0001f3b8", "✅", "✨", "❤"):
        assert EMOJI.search(ch)
    assert not EMOJI.search("Empório da Música — à vista · ação")
