"""Interface de linha de comando para conversar com a Mel (ARCHITECTURE §5.8.1)."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown

from emporio_agent import __version__
from emporio_agent.agent.agent import Agent, AgentReply
from emporio_agent.agent.session import Session
from emporio_agent.config import Settings, load_settings, now
from emporio_agent.data.loader import DataLoadError, load_all
from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.domain.store_hours import StoreStatus, store_status
from emporio_agent.llm.base import LLMClient, LLMError
from emporio_agent.llm.factory import create_llm_client
from emporio_agent.policies.store import PolicyStore, PolicyStoreError
from emporio_agent.tools import build_tool_registry

EXIT_OK = 0
EXIT_INIT_ERROR = 2

_WEEKDAYS = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)

HELP_TEXT = (
    "Comandos disponíveis:\n"
    "  /ajuda   mostra esta lista\n"
    "  /nova    inicia uma nova conversa\n"
    "  /salvar  grava a conversa em um arquivo .md\n"
    "  /sair    encerra o atendimento\n"
    "Opções de linha de comando: --debug, --save, --version (veja --help)."
)
FAREWELL = "Até logo! Obrigada por falar com o Empório da Música."


def build_agent(
    settings: Settings,
    *,
    llm: LLMClient | None = None,
    env: Mapping[str, str] | None = None,
) -> Agent:
    data = load_all(settings.data_dir)
    catalog = CatalogRepository(data)
    orders = OrderRepository(data)
    policies = PolicyStore.from_markdown(settings.policies_path)
    registry = build_tool_registry(
        catalog,
        orders,
        policies,
        clock=lambda: now(settings),
        runtime_dir=settings.runtime_dir,
    )
    return Agent(llm or create_llm_client(settings, env), registry, settings)


def greeting(current: datetime, status: StoreStatus) -> str:
    text = "Olá! Eu sou a Mel, assistente virtual do Empório da Música. Como posso ajudar?"
    if status.is_open_regular_hours:
        return f"{text}\n\nA loja está aberta agora (hoje, das {status.today_hours})."
    opening = status.next_opening
    if opening is None:  # defensivo: contrato garante next_opening quando fechada
        return f"{text}\n\nNo momento a loja está fechada."
    when = (
        f"{_WEEKDAYS[opening.weekday()]}, {opening:%d/%m} às {opening:%H:%M}"
    )
    return (
        f"{text}\n\nNo momento a loja está fechada pelo horário regular. "
        f"Voltamos a abrir {when}. Posso ajudar por aqui mesmo enquanto isso."
    )


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m emporio_agent",
        description="Converse com a Mel, assistente do Empório da Música.",
    )
    parser.add_argument("--debug", action="store_true", help="mostra as ferramentas usadas em cada resposta")
    parser.add_argument("--save", action="store_true", help="grava a conversa ao encerrar")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def _save_transcript(session: Session, settings: Settings) -> Path:
    directory = settings.runtime_dir / "transcripts"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = now(settings).strftime("%Y%m%d-%H%M%S")
    path = directory / f"conversa-{stamp}-{session.id}.md"
    path.write_text(session.to_markdown(), encoding="utf-8")
    return path


def _print_debug(console: Console, reply: AgentReply) -> None:
    for call in reply.tool_calls:
        if call.name == "consultar_pedido":
            args = {"pedido_id": call.arguments.get("pedido_id")}
        else:
            args = call.arguments
        status = "ok" if call.ok else "erro"
        console.print(
            f"[dim]  ferramenta: {call.name} {args} -> {status} ({call.duration_ms} ms)[/dim]",
            markup=True,
            highlight=False,
            soft_wrap=True,
        )
    console.print(f"[dim]  stop: {reply.stop}[/dim]", markup=True, highlight=False)


def main(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    llm: LLMClient | None = None,
    input_fn: Callable[[str], str] = input,
    console: Console | None = None,
) -> int:
    args = _parse_args(argv)
    if console is None:
        _configure_stdio()
        # Avisos de cadastro (loader) são para desenvolvedores, não para o cliente.
        logging.getLogger("emporio_agent").setLevel(logging.ERROR)
        console = Console()
    settings = settings or load_settings()

    try:
        agent = build_agent(settings, llm=llm)
    except LLMError as exc:
        console.print(f"Não foi possível iniciar o atendimento: {exc.message}", markup=False, highlight=False)
        return EXIT_INIT_ERROR
    except (DataLoadError, PolicyStoreError) as exc:
        console.print(f"Não foi possível carregar os dados da loja: {exc}", markup=False, highlight=False)
        return EXIT_INIT_ERROR

    def say(text: str) -> None:
        console.print("[bold green]Mel:[/bold green]", markup=True)
        console.print(Markdown(text))

    def new_session() -> Session:
        current = now(settings)
        say(greeting(current, store_status(current, settings.timezone)))
        return Session(started_at=current)

    session = new_session()
    try:
        while True:
            try:
                line = input_fn("Você: ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            text = line.strip()
            if not text:
                continue
            if text.startswith("/"):
                command = text.lower()
                if command == "/sair":
                    break
                if command == "/ajuda":
                    console.print(HELP_TEXT, markup=False, highlight=False)
                elif command == "/nova":
                    session = new_session()
                elif command == "/salvar":
                    path = _save_transcript(session, settings)
                    console.print(f"Conversa salva em: {path}", markup=False, highlight=False, soft_wrap=True)
                else:
                    console.print(
                        "Comando desconhecido. Digite /ajuda para ver os comandos.",
                        markup=False, highlight=False,
                    )
                continue
            try:
                with console.status("Mel está digitando..."):
                    reply = agent.respond(session, text)
            except KeyboardInterrupt:
                console.print()
                break
            say(reply.text)
            if args.debug:
                _print_debug(console, reply)
    finally:
        if args.save and session.messages:
            path = _save_transcript(session, settings)
            console.print(f"Conversa salva em: {path}", markup=False, highlight=False, soft_wrap=True)
    console.print(FAREWELL, markup=False, highlight=False)
    return EXIT_OK
