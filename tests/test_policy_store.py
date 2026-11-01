"""Testes da T07: PolicyStore (recuperação de políticas por tópico)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from emporio_agent.config import REPO_ROOT
from emporio_agent.policies.store import (
    POLICY_TOPICS,
    PolicySection,
    PolicyStore,
    PolicyStoreError,
)

POLICIES_MD = REPO_ROOT / "knowledge" / "policies.md"
SOURCE_PREFIX = "Manual de Políticas v2.1"


@pytest.fixture(scope="module")
def store() -> PolicyStore:
    return PolicyStore.from_markdown(POLICIES_MD)


def titles(sections: list[PolicySection]) -> list[str]:
    return [s.title for s in sections]


def joined(sections: list[PolicySection]) -> str:
    return "\n".join(s.text for s in sections)


def block(topic: str, title: str, body: str = "Corpo.") -> str:
    return f"<!-- topic: {topic} -->\n## {title}\n\n{body}\n\n"


def write_policies(tmp_path: Path, blocks: list[str], preamble: str = "# Manual\n\n> nota\n\n") -> Path:
    path = tmp_path / "policies.md"
    path.write_text(preamble + "".join(blocks), encoding="utf-8")
    return path


def full_blocks(skip: tuple[str, ...] = ()) -> list[str]:
    return [block(t, f"{i}. Seção {t}") for i, t in enumerate(POLICY_TOPICS, start=1) if t not in skip]


# --- arquivo versionado -------------------------------------------------------

def test_topics_constant():
    assert POLICY_TOPICS == (
        "sobre_loja", "horarios", "pagamento", "trocas_devolucoes", "frete_entrega",
        "promocoes", "atendimento", "garantia", "privacidade",
    )


def test_eleven_sections_and_topics_order(store):
    assert len(store.sections()) == 11
    assert store.topics() == list(POLICY_TOPICS)


def test_sections_are_policy_sections(store):
    assert all(isinstance(s, PolicySection) for s in store.sections())


def test_sections_in_document_order(store):
    assert titles(store.sections()) == [
        "Capa",
        "1. Sobre a Empório da Música",
        "2. Horário de Funcionamento",
        "3. Formas de Pagamento",
        "4. Política de Trocas e Devoluções",
        "5. Política de Frete e Entregas",
        "6. Promoções e Descontos",
        "7. Atendimento via WhatsApp",
        "8. Garantia",
        "9. Privacidade e Proteção de Dados",
        "10. Disposições Finais",
    ]


def test_sobre_loja_has_cover_and_section_1(store):
    assert titles(store.get("sobre_loja")) == ["Capa", "1. Sobre a Empório da Música"]


def test_atendimento_has_sections_7_and_10(store):
    assert titles(store.get("atendimento")) == ["7. Atendimento via WhatsApp", "10. Disposições Finais"]


@pytest.mark.parametrize("topic", POLICY_TOPICS)
def test_every_topic_has_sections_with_matching_topic(store, topic):
    sections = store.get(topic)
    assert sections
    assert all(s.topic == topic for s in sections)


def test_sources(store):
    cover, first = store.get("sobre_loja")
    assert cover.source == f"{SOURCE_PREFIX}, capa"
    assert first.source == f"{SOURCE_PREFIX}, seção 1"
    assert store.get("atendimento")[1].source == f"{SOURCE_PREFIX}, seção 10"
    assert store.get("trocas_devolucoes")[0].source == f"{SOURCE_PREFIX}, seção 4"


def test_email_spellings_preserved_p2(store):
    cover, first = store.get("sobre_loja")
    assert "contato@emporiodamusica.com.br" in cover.text
    assert "contato@empóriodamusica.com.br" not in cover.text
    assert "contato@empóriodamusica.com.br" in first.text


def test_trocas_content(store):
    text = joined(store.get("trocas_devolucoes"))
    assert "7 (sete) dias" in text
    assert "30 (trinta) dias" in text


def test_pagamento_content(store):
    text = joined(store.get("pagamento"))
    assert "5% de desconto" in text
    assert "| Forma | Condições | Observações |" in text
    assert "### 3.1 Regras de Parcelamento" in text
    assert "Parcelamento em até 3x" in text
    assert "Parcelamento de 4x a 6x" in text
    assert "Parcelamento de 7x a 12x" in text


def test_text_is_clean(store):
    for s in store.sections():
        assert "<!--" not in s.text
        assert not s.text.startswith("## ")
        assert f"## {s.title}" not in s.text
        assert s.text == s.text.strip()
        lines = s.text.splitlines()
        assert lines[0].strip() != ""
        assert lines[-1].strip() != ""


def test_markdown_preserved(store):
    pagamento = store.get("pagamento")[0].text
    assert "### 3.1" in pagamento
    assert "|---|" in pagamento
    assert "- Parcelamento" in pagamento
    assert "**" in store.get("sobre_loja")[0].text  # negrito da capa


def test_get_unknown_topic_raises_key_error(store):
    with pytest.raises(KeyError):
        store.get("inexistente")


def test_get_returns_independent_list(store):
    first = store.get("sobre_loja")
    first.clear()
    assert len(store.get("sobre_loja")) == 2


def test_sections_equals_concatenation_of_topics(store):
    by_topic = [s for t in store.topics() for s in store.get(t)]
    assert sorted(titles(by_topic)) == sorted(titles(store.sections()))


def test_reading_does_not_modify_file():
    before = hashlib.sha256(POLICIES_MD.read_bytes()).hexdigest()
    mtime = POLICIES_MD.stat().st_mtime_ns
    PolicyStore.from_markdown(POLICIES_MD).sections()
    assert hashlib.sha256(POLICIES_MD.read_bytes()).hexdigest() == before
    assert POLICIES_MD.stat().st_mtime_ns == mtime


# --- arquivos temporários -----------------------------------------------------

def test_minimal_valid_file(tmp_path):
    store = PolicyStore.from_markdown(write_policies(tmp_path, full_blocks()))
    assert len(store.sections()) == 9
    section = store.get("horarios")[0]
    assert section.title == "2. Seção horarios"
    assert section.source == f"{SOURCE_PREFIX}, seção 2"
    assert section.text == "Corpo."


def test_preamble_before_first_marker_is_ignored(tmp_path):
    path = write_policies(tmp_path, full_blocks(), preamble="# Título\n\nlixo antes\n\n")
    store = PolicyStore.from_markdown(path)
    assert "lixo" not in joined(store.sections())


def test_text_is_stripped_of_blank_edges(tmp_path):
    blocks = full_blocks(skip=("garantia",)) + [
        "<!-- topic: garantia -->\n\n\n## 8. Garantia\n\n\nlinha\n\n\n\n"
    ]
    store = PolicyStore.from_markdown(write_policies(tmp_path, blocks))
    assert store.get("garantia")[0].text == "linha"


def test_missing_topic_lists_missing(tmp_path):
    path = write_policies(tmp_path, full_blocks(skip=("garantia", "privacidade")))
    with pytest.raises(PolicyStoreError) as exc:
        PolicyStore.from_markdown(path)
    assert "garantia" in str(exc.value)
    assert "privacidade" in str(exc.value)
    assert "horarios" not in str(exc.value)


def test_unknown_topic_marker(tmp_path):
    path = write_policies(tmp_path, full_blocks() + [block("desconhecido", "11. X")])
    with pytest.raises(PolicyStoreError) as exc:
        PolicyStore.from_markdown(path)
    assert "desconhecido" in str(exc.value)


def test_block_without_h2_heading(tmp_path):
    bad = "<!-- topic: garantia -->\nTexto sem título\n\n"
    path = write_policies(tmp_path, full_blocks(skip=("garantia",)) + [bad])
    with pytest.raises(PolicyStoreError):
        PolicyStore.from_markdown(path)


def test_nonexistent_file(tmp_path):
    missing = tmp_path / "nao_existe.md"
    with pytest.raises(PolicyStoreError) as exc:
        PolicyStore.from_markdown(missing)
    assert "nao_existe.md" in str(exc.value)


def test_error_is_exception_not_key_error():
    assert issubclass(PolicyStoreError, Exception)
    assert not issubclass(PolicyStoreError, KeyError)


def test_cover_source_in_tmp_file(tmp_path):
    blocks = [block("sobre_loja", "Capa")] + full_blocks(skip=("sobre_loja",))
    store = PolicyStore.from_markdown(write_policies(tmp_path, blocks))
    assert store.get("sobre_loja")[0].source == f"{SOURCE_PREFIX}, capa"


def test_tmp_file_not_modified(tmp_path):
    path = write_policies(tmp_path, full_blocks())
    before = path.read_bytes()
    PolicyStore.from_markdown(path).sections()
    assert path.read_bytes() == before
