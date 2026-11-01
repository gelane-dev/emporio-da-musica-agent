"""Normalização de texto para busca (sem acentos, sem caixa, plural simplificado)."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Palavras sem valor de busca em consultas de clientes.
STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "as", "o", "os", "um", "uma", "uns", "umas", "de", "da", "das", "do", "dos",
        "e", "em", "na", "nas", "no", "nos", "para", "pra", "por", "com", "que", "qual",
        "quais", "ate", "tem", "voces", "vcs", "me", "eu", "quero",
    }
)


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(text: str) -> str:
    """Minúsculas, sem acentos, só letras/dígitos separados por um espaço."""
    return _NON_ALNUM.sub(" ", strip_accents(text).lower()).strip()


def compact(text: str) -> str:
    """Forma normalizada sem espaços — útil para códigos de modelo (``GD-20`` → ``gd20``)."""
    return normalize(text).replace(" ", "")


def stem(token: str) -> str:
    """Reduz plurais comuns do português ao singular (``violoes`` → ``violao``)."""
    if len(token) <= 3 or token.isdigit():
        return token
    if token.endswith("oes") or token.endswith("aes"):
        return token[:-3] + "ao"
    if token.endswith("ais"):
        return token[:-3] + "al"
    if token.endswith("eis"):
        return token[:-3] + "el"
    if token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text: str, *, drop_stopwords: bool = True) -> list[str]:
    """Tokens normalizados e no singular."""
    result = []
    for token in normalize(text).split():
        if drop_stopwords and token in STOPWORDS:
            continue
        result.append(stem(token))
    return result
