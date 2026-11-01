"""Testes da T11 (parte Session): ARCHITECTURE §5.7.2 (``agent/session.py``)."""

from __future__ import annotations

import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.agent.session import Session
from emporio_agent.llm.base import Message, ToolCall

TZ = ZoneInfo("America/Campo_Grande")
START = datetime(2026, 11, 1, 15, 47, tzinfo=TZ)


def user(text: str) -> Message:
    return Message(role="user", content=text)


def assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def assistant_tools(*calls: tuple[str, str, dict]) -> Message:
    return Message(
        role="assistant",
        tool_calls=[ToolCall(id=i, name=n, arguments=a) for i, n, a in calls],
        provider_content=[{"type": "thinking", "thinking": "SEGREDO_RACIOCINIO", "signature": "sig"}],
    )


def tool_result(call_id: str, content: str = '{"ok":true}', is_error: bool = False) -> Message:
    return Message(role="tool", tool_call_id=call_id, content=content, is_error=is_error)


def add_plain_turn(session: Session, n: int) -> None:
    session.add_user(f"pergunta {n}")
    session.add(assistant(f"resposta {n}"))


def add_tool_turn(session: Session, n: int, calls: int = 2) -> None:
    session.add_user(f"pergunta {n}")
    ids = [f"t{n}_{k}" for k in range(calls)]
    session.add(assistant_tools(*[(i, "listar_categorias", {}) for i in ids]))
    for i in ids:
        session.add(tool_result(i))
    session.add(assistant(f"resposta {n}"))


def assert_valid_window(window: list[Message]) -> None:
    """Invariantes: começa em user; todo resultado tem a tool call antes; toda tool call tem resultado."""
    assert window, "janela vazia"
    assert window[0].role == "user"
    pending: set[str] = set()
    for i, msg in enumerate(window):
        if msg.role == "assistant":
            pending = {c.id for c in msg.tool_calls}
        elif msg.role == "tool":
            assert msg.tool_call_id in pending, f"resultado órfão na posição {i}"
            pending.discard(msg.tool_call_id)
        elif msg.role == "user" and i > 0:
            assert not pending, "tool call sem resultado antes do próximo turno"
    assert not pending


# ----------------------------------------------------------------------------- construção


def test_construcao_padrao():
    session = Session(START)
    assert session.started_at == START
    assert session.messages == []
    assert re.fullmatch(r"[0-9a-f]{8}", session.id)


def test_ids_padrao_diferem_e_id_explicito_e_respeitado():
    assert Session(START).id != Session(START).id
    assert Session(START, session_id="abc123").id == "abc123"


def test_add_user_e_add_acrescentam_em_ordem():
    session = Session(START)
    session.add_user("oi")
    session.add(assistant("olá"))
    assert [m.role for m in session.messages] == ["user", "assistant"]
    assert session.messages[0].content == "oi"
    assert session.messages[1].content == "olá"


# ----------------------------------------------------------------------------- window


def test_window_historico_curto_devolve_tudo():
    session = Session(START)
    add_plain_turn(session, 1)
    add_tool_turn(session, 2)
    assert session.window(5) == session.messages
    assert session.window(2) == session.messages  # exatamente max_turns turnos


def test_window_sessao_vazia():
    assert Session(START).window(3) == []


def test_window_devolve_copia():
    session = Session(START)
    add_plain_turn(session, 1)
    window = session.window(10)
    assert window is not session.messages
    window.clear()
    assert len(session.messages) == 2


def test_window_nao_altera_historico():
    session = Session(START)
    for n in range(1, 6):
        add_tool_turn(session, n)
    before = list(session.messages)
    session.window(2)
    assert session.messages == before


def test_window_corta_no_inicio_do_turno_mais_antigo_mantido():
    session = Session(START)
    for n in range(1, 6):
        add_plain_turn(session, n)
    window = session.window(2)
    assert [m.content for m in window] == ["pergunta 4", "resposta 4", "pergunta 5", "resposta 5"]


def test_window_turno_com_tools_fica_inteiro():
    session = Session(START)
    add_plain_turn(session, 1)
    add_tool_turn(session, 2, calls=3)
    add_tool_turn(session, 3, calls=2)
    window = session.window(2)
    assert window[0].content == "pergunta 2"
    assert [m.role for m in window] == [
        "user", "assistant", "tool", "tool", "tool", "assistant",
        "user", "assistant", "tool", "tool", "assistant",
    ]
    assert_valid_window(window)


def test_window_max_turns_1_pega_so_o_ultimo_turno_com_tools():
    session = Session(START)
    add_tool_turn(session, 1)
    add_tool_turn(session, 2)
    window = session.window(1)
    assert window[0].content == "pergunta 2"
    assert len(window) == 5
    assert_valid_window(window)


def test_window_historico_longo_nunca_comeca_fora_de_user_nem_separa_tools():
    session = Session(START)
    for n in range(1, 16):
        if n % 3 == 0:
            add_tool_turn(session, n, calls=n % 4 + 1)
        else:
            add_plain_turn(session, n)
    for max_turns in range(1, 18):
        window = session.window(max_turns)
        assert_valid_window(window)
        turns = sum(1 for m in window if m.role == "user")
        assert turns == min(max_turns, 15)


def test_window_turno_em_andamento_sem_resposta_final():
    """Durante o laço do agente o último turno ainda não terminou: tool calls + resultados, sem texto final."""
    session = Session(START)
    add_plain_turn(session, 1)
    session.add_user("pergunta 2")
    session.add(assistant_tools(("a", "listar_categorias", {}), ("b", "listar_categorias", {})))
    session.add(tool_result("a"))
    session.add(tool_result("b"))
    window = session.window(1)
    assert [m.role for m in window] == ["user", "assistant", "tool", "tool"]
    assert_valid_window(window)


def test_window_preserva_provider_content_sem_edicao():
    session = Session(START)
    add_tool_turn(session, 1)
    window = session.window(5)
    assistente = next(m for m in window if m.tool_calls)
    assert assistente.provider_content == [
        {"type": "thinking", "thinking": "SEGREDO_RACIOCINIO", "signature": "sig"}
    ]


# ----------------------------------------------------------------------------- to_markdown


def test_markdown_cabecalho():
    session = Session(START, session_id="abc12345")
    md = session.to_markdown()
    assert md.startswith("# Conversa — Empório da Música")
    assert "abc12345" in md
    assert "01/11/2026 15:47" in md


def test_markdown_falas_em_ordem():
    session = Session(START)
    add_plain_turn(session, 1)
    add_plain_turn(session, 2)
    md = session.to_markdown()
    posicoes = [
        md.index("**Cliente:** pergunta 1"),
        md.index("**Mel:** resposta 1"),
        md.index("**Cliente:** pergunta 2"),
        md.index("**Mel:** resposta 2"),
    ]
    assert posicoes == sorted(posicoes)


def test_markdown_linhas_de_ferramenta_com_status():
    session = Session(START)
    session.add_user("quero ver o pedido")
    session.add(assistant_tools(("c1", "consultar_pedido", {"pedido_id": 19}), ("c2", "listar_categorias", {})))
    session.add(tool_result("c1", '{"ok":false,"erro":{"codigo":"VERIFICATION_FAILED"}}', is_error=True))
    session.add(tool_result("c2", '{"ok":true,"dados":[]}'))
    session.add(assistant("Não consegui verificar."))
    md = session.to_markdown()

    erro = re.search(r"> Ferramenta: `consultar_pedido` \{\"pedido_id\":\s?19\}[^\n]*", md)
    ok = re.search(r"> Ferramenta: `listar_categorias` \{\}[^\n]*", md)
    assert erro and "(erro)" in erro.group(0) and "(ok)" not in erro.group(0)
    assert ok and "(ok)" in ok.group(0) and "(erro)" not in ok.group(0)
    assert md.index("consultar_pedido") < md.index("listar_categorias") < md.index("**Mel:** Não consegui")


def test_markdown_nao_inclui_provider_content_nem_json_dos_resultados():
    session = Session(START)
    add_tool_turn(session, 1)
    md = session.to_markdown()
    assert "SEGREDO_RACIOCINIO" not in md
    assert "thinking" not in md
    assert '{"ok":true}' not in md


def test_markdown_sessao_vazia_so_cabecalho():
    md = Session(START).to_markdown()
    assert "**Cliente:**" not in md
    assert "**Mel:**" not in md


@pytest.mark.parametrize("max_turns", [1, 3])
def test_markdown_usa_historico_completo_nao_a_janela(max_turns):
    session = Session(START)
    for n in range(1, 6):
        add_plain_turn(session, n)
    session.window(max_turns)
    md = session.to_markdown()
    assert "pergunta 1" in md and "resposta 5" in md
