"""Gravação de conversas reais de exemplo (ARCHITECTURE §5.9.2, TASKS T15).

Lê um roteiro de falas do cliente (uma por linha), conversa com o agente real usando
o mesmo ``Agent``/``Session``/``Session.to_markdown()`` do comando ``/salvar`` da CLI e
grava o transcript sem editar nenhum texto do agente. Sem credencial: código 2.
Se alguma resposta falhar (``llm_error``): código 3 e nada é gravado.

Uso::

    python scripts/record_example.py --script roteiro.txt --out saida.md \
        [--title TEXTO] [--reference-date 2026-03-25T10:00] [--pause 20] [--force]
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from emporio_agent.agent.session import Session
from emporio_agent.cli import build_agent
from emporio_agent.config import REPO_ROOT, load_settings, now, parse_reference_date
from emporio_agent.data.loader import DataLoadError
from emporio_agent.llm.base import LLMError
from emporio_agent.policies.store import PolicyStoreError

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_INIT_ERROR = 2
EXIT_LLM_ERROR = 3

DEFAULT_REFERENCE_DATE = "2026-03-25T10:00"
DEFAULT_PAUSE = 20.0  # segundos entre turnos (limite de tokens/min da Groq)


def read_script(path: Path) -> list[str]:
    """Falas do roteiro: ignora linhas vazias e as iniciadas por '#'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def git_short_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"
    return result.stdout.strip() or "desconhecido"


def build_header(
    title: str,
    recorded_at: datetime,
    provider: str,
    model: str,
    effort: str,
    reference_date: datetime,
    commit: str,
) -> str:
    return "\n".join(
        [
            f"# Exemplo — {title}",
            "",
            f"> Gravada em: {recorded_at:%d/%m/%Y %H:%M} (data real da gravação)  ",
            f"> Provedor/modelo: {provider} / {model} (LLM_EFFORT={effort})  ",
            f"> Data de referência do agente: {reference_date:%d/%m/%Y %H:%M}  ",
            f"> Commit: {commit}  ",
            "> Conversa real, transcrita sem edição por scripts/record_example.py.",
            "",
            "",
        ]
    )


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grava uma conversa real de exemplo a partir de um roteiro.")
    parser.add_argument("--script", type=Path, required=True, help="roteiro: uma fala do cliente por linha")
    parser.add_argument("--out", type=Path, required=True, help="arquivo Markdown de saída")
    parser.add_argument("--title", help="título do cabeçalho (padrão: nome do roteiro)")
    parser.add_argument(
        "--reference-date", default=DEFAULT_REFERENCE_DATE, help=f"data/hora ISO (padrão {DEFAULT_REFERENCE_DATE})"
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=DEFAULT_PAUSE,
        metavar="SEGUNDOS",
        help=f"pausa entre turnos (padrão {DEFAULT_PAUSE:g})",
    )
    parser.add_argument("--force", action="store_true", help="sobrescreve o arquivo de saída se já existir")
    args = parser.parse_args(argv)

    _configure_stdio()
    logging.getLogger("emporio_agent").setLevel(logging.ERROR)

    if args.pause < 0:
        print("--pause deve ser >= 0", file=sys.stderr)
        return EXIT_INIT_ERROR
    if args.out.exists() and not args.force:
        print(f"{args.out} já existe; use --force para sobrescrever.", file=sys.stderr)
        return EXIT_INIT_ERROR
    try:
        turns = read_script(args.script)
    except OSError as exc:
        print(f"Não foi possível ler o roteiro: {exc}", file=sys.stderr)
        return EXIT_INIT_ERROR
    if not turns:
        print(f"O roteiro {args.script} não tem falas.", file=sys.stderr)
        return EXIT_INIT_ERROR

    try:
        settings = load_settings()
        settings = settings.model_copy(
            update={"reference_datetime": parse_reference_date(args.reference_date, settings.timezone)}
        )
        agent = build_agent(settings)
    except LLMError as exc:
        print(f"Não foi possível gravar a conversa: {exc.message}", file=sys.stderr)
        return EXIT_INIT_ERROR
    except (DataLoadError, PolicyStoreError, ValueError) as exc:
        print(f"Não foi possível gravar a conversa: {exc}", file=sys.stderr)
        return EXIT_INIT_ERROR

    session = Session(started_at=now(settings))
    for index, text in enumerate(turns, start=1):
        if index > 1 and args.pause > 0:
            time.sleep(args.pause)
        print(f"[{index}/{len(turns)}] Cliente: {text}")
        reply = agent.respond(session, text)
        if reply.stop == "llm_error":
            print(f"Falha do LLM no turno {index}; nada foi gravado.", file=sys.stderr)
            return EXIT_LLM_ERROR

    title = args.title or args.script.stem
    header = build_header(
        title,
        datetime.now().astimezone(),
        settings.llm_provider,
        settings.llm_model,
        settings.llm_effort,
        settings.reference_datetime or now(settings),
        git_short_hash(),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(header + session.to_markdown(), encoding="utf-8")
    print(f"Conversa gravada em {args.out}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
