"""Proteção de saída (ARCHITECTURE §5.7.2): sem emojis e com hifens tipográficos normalizados."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from emporio_agent.agent.output_guard import normalize_typography, sanitize_reply, strip_emojis
from emporio_agent.agent.session import Session
from emporio_agent.cli import build_agent
from emporio_agent.config import Settings
from fakes import FakeLLM, fake_text

MONDAY = datetime(2026, 3, 25, 10, 0, tzinfo=ZoneInfo("America/Campo_Grande"))


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Pronto! 😊", "Pronto!"),
        ("Olá 🎸🎹 tudo bem?", "Olá tudo bem?"),
        ("Boa 👍🏽", "Boa"),
        ("Família 👨‍👩‍👧 aqui", "Família aqui"),
        ("Coração ❤️ ok", "Coração ok"),
        ("Bandeira 🇧🇷 ok", "Bandeira ok"),
        ("Estrela ⭐ e raio ⚡", "Estrela e raio"),
    ],
)
def test_strip_emojis_removes_emoji(text, expected):
    assert strip_emojis(text) == expected


def test_strip_emojis_leaves_no_zwj_or_variation_selector():
    out = strip_emojis("a 👨‍👩‍👧 b ❤️ c")
    assert "\u200d" not in out and "\ufe0f" not in out


def test_strip_emojis_preserves_simple_arrows():
    assert strip_emojis("A → B ← C ↑ D ↓ E ↔ F") == "A → B ← C ↑ D ↓ E ↔ F"


def test_strip_emojis_preserves_accents_and_currency():
    text = "Preço: R$ 1.234,56 — ação, coração, pão"
    assert strip_emojis(text) == text


def test_strip_emojis_preserves_line_breaks():
    assert strip_emojis("linha 1 😊\nlinha 2\n\nlinha 3") == "linha 1\nlinha 2\n\nlinha 3"


def test_strip_emojis_collapses_double_spaces():
    assert strip_emojis("antes 😊 depois") == "antes depois"
    assert strip_emojis("antes  😊  depois") == "antes depois"


def test_strip_emojis_preserves_existing_spaces_without_emoji():
    assert strip_emojis("um  dois   três") == "um  dois   três"


def test_strip_emojis_preserves_indented_markdown_list():
    text = "- item\n  - subitem\n    - sub-subitem"
    assert strip_emojis(text) == text


def test_strip_emojis_plain_text_unchanged():
    assert strip_emojis("Texto simples.") == "Texto simples."


def test_normalize_typography_replaces_non_breaking_hyphens():
    assert normalize_typography("(67) 3341\u20114444") == "(67) 3341-4444"
    assert normalize_typography("a\u2010b") == "a-b"


def test_normalize_typography_leaves_plain_text():
    assert normalize_typography("(67) 3341-4444 ação") == "(67) 3341-4444 ação"


def test_sanitize_reply_combines_both():
    assert sanitize_reply("Ligue (67) 3341\u20114444 😊") == "Ligue (67) 3341-4444"
    assert sanitize_reply("a\nb") == "a\nb"


def test_agent_reply_and_session_message_have_no_emoji():
    settings = Settings(reference_datetime=MONDAY)
    llm = FakeLLM([fake_text("Pronto! 😊")])
    session = Session(started_at=MONDAY)
    reply = build_agent(settings, llm=llm).respond(session, "oi")

    assert reply.text == "Pronto!"
    assistant = [m for m in session.messages if m.role == "assistant"]
    assert [m.content for m in assistant] == ["Pronto!"]
