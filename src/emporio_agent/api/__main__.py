"""Executa a API: ``python -m emporio_agent.api`` (uvicorn; padrão 127.0.0.1:8000).

``API_HOST`` e ``API_PORT`` (ambiente ou ``.env``) mudam o endereço; o contêiner usa ``API_HOST=0.0.0.0``.
"""

from __future__ import annotations

import logging

import uvicorn

from emporio_agent.config import read_env

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def server_address(values: dict[str, str]) -> tuple[str, int]:
    """Host e porta a partir de ``API_HOST``/``API_PORT``; valores vazios usam o padrão."""
    host = (values.get("API_HOST") or "").strip() or DEFAULT_HOST
    raw_port = (values.get("API_PORT") or "").strip()
    if not raw_port:
        return host, DEFAULT_PORT
    try:
        port = int(raw_port)
    except ValueError:
        raise SystemExit(f"API_PORT inválida: {raw_port!r} (use um número entre 1 e 65535).") from None
    if not 1 <= port <= 65535:
        raise SystemExit(f"API_PORT inválida: {port} (use um número entre 1 e 65535).")
    return host, port


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Avisos de cadastro (loader) são para desenvolvedores; mantém só erros.
    logging.getLogger("emporio_agent.data").setLevel(logging.ERROR)
    host, port = server_address(read_env())
    uvicorn.run("emporio_agent.api.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
