"""Proteção de saída: garante por código "sem emojis" e telefones copiáveis (ARCHITECTURE §5.7.2)."""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable

from emporio_agent.llm.base import Message

logger = logging.getLogger(__name__)

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


# Formato real gerado por encaminhar_atendente: EM-AAAAMMDD-XXXXXX (6 hex maiúsculos).
# Rastreio dos CSVs (BRAB1234567BR) e o formato padrão dos Correios (AA123456789BR).
# A busca roda sobre o texto normalizado (_normalize): maiúsculas, sem caracteres invisíveis.
# Separadores tolerados: espaços, hífen, travessões e sinal de menos (até 3 seguidos).
_SEP = r"[\s\-\u2010-\u2015\u2212]{0,3}"
_START, _END = r"(?<![A-Z0-9])", r"(?![A-Z0-9])"
_PROTOCOL_RE = re.compile(_START + r"EM" + _SEP + r"\d{8}" + _SEP + r"[0-9A-F]{6}" + _END)
# Rastreio compacto (como sai das ferramentas): qualquer sufixo de 2 letras, como antes.
_TRACKING_RE = re.compile(_START + r"(?:[A-Z]{4}\d{7}[A-Z]{2}|[A-Z]{2}\d{9}[A-Z]{2})" + _END)
# Rastreio com separadores: só com sufixo BR (todos os rastreios da loja). Sem essa âncora,
# frases comuns ("para 1234567 de") virariam falso positivo.
_TRACKING_SPACED_RE = re.compile(
    _START + r"(?:[A-Z]{4}" + _SEP + r"\d{7}|[A-Z]{2}" + _SEP + r"\d{9})" + _SEP + r"BR" + _END
)
# Invisíveis que o modelo (ou uma injeção) pode inserir no meio de um código para escapar da busca.
_INVISIBLE_RE = re.compile(r"[\u00ad\u180e\u200b-\u200f\u2060-\u2064\ufeff]")
_NOT_ALNUM_RE = re.compile(r"[^A-Z0-9]")


def _normalize(text: str) -> str:
    return _INVISIBLE_RE.sub("", unicodedata.normalize("NFKC", text)).upper()


UNVERIFIED_CODE_REPLY = (
    "Desculpe, não consegui confirmar essa informação agora. Pode repetir o que você precisa? "
    "Se preferir, nossa equipe pode ajudar diretamente."
)


def _codes(text: str) -> set[str]:
    """Códigos citados em forma canônica (só letras e dígitos), para comparar variações de escrita."""
    normalized = _normalize(text)
    found = (
        _PROTOCOL_RE.findall(normalized)
        + _TRACKING_RE.findall(normalized)
        + _TRACKING_SPACED_RE.findall(normalized)
    )
    return {_NOT_ALNUM_RE.sub("", code) for code in found}


def guard_reply(text: str, messages: Iterable[Message]) -> str:
    """Barra protocolo/rastreio que não veio de ferramenta nem do cliente nesta sessão.

    Risco: o modelo (induzido por injeção de prompt ou alucinando) inventa um protocolo de
    atendimento ou código de rastreio e o cliente passa a confiar nele. Checagem por código:
    todo código citado precisa ter aparecido num resultado de ferramenta ou ter sido digitado pelo
    próprio cliente (ecoar o código que ele informou não é invenção). Sem regex para preços
    ou veredictos (falsos positivos). O log não inclui o conteúdo.
    """
    cited = _codes(text)
    if not cited:
        return text
    known: set[str] = set()
    for message in messages:
        if message.role in ("tool", "user") and message.content:
            known |= _codes(message.content)
    if cited - known:
        logger.warning("Resposta bloqueada: código de protocolo/rastreio sem origem na sessão.")
        return UNVERIFIED_CODE_REPLY
    return text
