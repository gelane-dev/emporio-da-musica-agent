"""Proteção de saída: garante por código "sem emojis" e telefones copiáveis (ARCHITECTURE §5.7.2)."""

from __future__ import annotations

import re

# Mesmas faixas de scripts/run_scenarios.has_emoji.
_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # símbolos, emoticons, transporte, suplementares
    "\U00002600-\U000027bf"  # símbolos diversos e dingbats
    "\U00002b00-\U00002bff"  # setas e estrelas
    "\U00002300-\U000023ff"  # técnicos
    "\U0000fe0f\U0000200d"  # seletor de variação e junção de largura zero
    "\U0001f1e6-\U0001f1ff"  # bandeiras
    "\U00002190-\U000021ff"  # setas
    "]"
)
# Setas simples são tipografia legítima, não emoji.
_ALLOWED = frozenset("←→↑↓↔")
_RUN_RE = re.compile(
    r"([ \t]*)((?:(?![←→↑↓↔])" + _EMOJI_RE.pattern + r")+)([ \t]*)"
)


def strip_emojis(text: str) -> str:
    """Remove emojis/pictogramas e colapsa só os espaços duplicados no ponto da remoção."""

    def _drop(match: re.Match[str]) -> str:
        before, after = match.group(1), match.group(3)
        start, end = match.start(), match.end()
        at_line_start = start == 0 or text[start - 1] == "\n"
        if end == len(text) or text[end] == "\n":
            # Fim de linha: sem espaço sobrando (linha só de emoji mantém a indentação).
            return before if at_line_start else ""
        if at_line_start:
            return before
        # Texto dos dois lados: toda a sequência de espaços vira um só.
        return " " if (before or after) else ""

    return _RUN_RE.sub(_drop, text)


def normalize_typography(text: str) -> str:
    """Troca hifens tipográficos (U+2010, U+2011) por '-', para telefones copiáveis."""
    return text.replace("‐", "-").replace("‑", "-")


def sanitize_reply(text: str) -> str:
    return normalize_typography(strip_emojis(text))
