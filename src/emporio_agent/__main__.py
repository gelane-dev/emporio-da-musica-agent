"""Ponto de entrada: ``python -m emporio_agent``.

Por enquanto apenas exibe a versão; a CLI de conversa é implementada na T13.
"""

from emporio_agent import __version__


def main() -> None:
    print(f"Empório da Música — agente de atendimento v{__version__}")


if __name__ == "__main__":
    main()
