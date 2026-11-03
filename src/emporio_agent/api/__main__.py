"""Executa a API: ``python -m emporio_agent.api`` (uvicorn em 127.0.0.1:8000)."""

from __future__ import annotations

import logging

import uvicorn


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    # Avisos de cadastro (loader) são para desenvolvedores; mantém só erros.
    logging.getLogger("emporio_agent.data").setLevel(logging.ERROR)
    uvicorn.run("emporio_agent.api.app:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
