"""Acesso por tópico ao ``knowledge/policies.md`` (T07; ARCHITECTURE §5.4.2).

O arquivo é dividido em blocos iniciados por ``<!-- topic: X -->`` seguido de
uma linha ``## Título``. Conteúdo antes do primeiro marcador (H1 e nota de
extração) é ignorado.

Tópico com vários blocos: ``get`` devolve todos, na ordem do documento
(``sobre_loja`` ⇒ "Capa" e "1. Sobre a Empório da Música"; ``atendimento`` ⇒
"7. Atendimento via WhatsApp" e "10. Disposições Finais").

A Capa é mantida (não descartada nem fundida): contém a grafia do e-mail sem
acento e o telefone (DATA_ANALYSIS P1/P2).

Somente leitura; o texto não é reinterpretado nem corrigido.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

POLICY_TOPICS: tuple[str, ...] = (
    "sobre_loja",
    "horarios",
    "pagamento",
    "trocas_devolucoes",
    "frete_entrega",
    "promocoes",
    "atendimento",
    "garantia",
    "privacidade",
)

PolicyTopic = Literal[
    "sobre_loja",
    "horarios",
    "pagamento",
    "trocas_devolucoes",
    "frete_entrega",
    "promocoes",
    "atendimento",
    "garantia",
    "privacidade",
]

_MARKER_RE = re.compile(r"^<!--\s*topic:\s*(\S+)\s*-->\s*$")
_NUMBER_RE = re.compile(r"^(\d+)\.")
_SOURCE_PREFIX = "Manual de Políticas v2.1"


class PolicyStoreError(Exception):
    """Arquivo ausente ou malformado; a mensagem cita o arquivo e o motivo."""


class PolicySection(BaseModel, frozen=True):
    topic: PolicyTopic
    title: str
    source: str
    text: str


def _build_source(title: str) -> str:
    match = _NUMBER_RE.match(title)
    if match:
        return f"{_SOURCE_PREFIX}, seção {match.group(1)}"
    return f"{_SOURCE_PREFIX}, capa"


class PolicyStore:
    def __init__(self, sections: list[PolicySection]) -> None:
        self._sections = list(sections)

    @classmethod
    def from_markdown(cls, path: Path) -> "PolicyStore":
        path = Path(path)
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise PolicyStoreError(f"{path}: arquivo não encontrado") from None
        except (OSError, UnicodeDecodeError) as exc:
            raise PolicyStoreError(f"{path}: não foi possível ler ({exc})") from exc

        # Agrupa as linhas por bloco, ignorando o que vem antes do 1º marcador.
        blocks: list[tuple[str, list[str]]] = []
        for line in content.splitlines():
            marker = _MARKER_RE.match(line.strip())
            if marker:
                blocks.append((marker.group(1), []))
            elif blocks:
                blocks[-1][1].append(line)

        sections: list[PolicySection] = []
        for topic, lines in blocks:
            if topic not in POLICY_TOPICS:
                raise PolicyStoreError(f"{path}: marcador com tópico desconhecido '{topic}'")
            while lines and not lines[0].strip():
                lines.pop(0)
            if not lines or not lines[0].startswith("## "):
                raise PolicyStoreError(
                    f"{path}: bloco do tópico '{topic}' não começa com um título '## '"
                )
            title = lines[0][3:].strip()
            body = lines[1:]
            while body and not body[0].strip():
                body.pop(0)
            while body and not body[-1].strip():
                body.pop()
            sections.append(
                PolicySection(
                    topic=topic,  # type: ignore[arg-type]
                    title=title,
                    source=_build_source(title),
                    text="\n".join(body),
                )
            )

        present = {s.topic for s in sections}
        missing = [t for t in POLICY_TOPICS if t not in present]
        if missing:
            raise PolicyStoreError(f"{path}: tópicos ausentes: {', '.join(missing)}")
        return cls(sections)

    def get(self, topic: str) -> list[PolicySection]:
        if topic not in POLICY_TOPICS:
            raise KeyError(topic)
        return [s for s in self._sections if s.topic == topic]

    def topics(self) -> list[str]:
        return list(POLICY_TOPICS)

    def sections(self) -> list[PolicySection]:
        return list(self._sections)
