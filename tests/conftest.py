"""Fixtures compartilhadas."""

from __future__ import annotations

from pathlib import Path

import pytest

from emporio_agent.config import REPO_ROOT
from emporio_agent.data.loader import load_all
from emporio_agent.data.models import StoreData

DATA_DIR: Path = REPO_ROOT / "data"


CREDENTIAL_VARS: tuple[str, ...] = ("GROQ_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


@pytest.fixture(autouse=True)
def _isolate_llm_credentials(request, monkeypatch):
    """Testes comuns nunca alcançam um provedor real, com ou sem ``.env``.

    O ambiente tem prioridade sobre o ``.env`` em ``read_env`` e chave vazia = ausente.
    Testes marcados com ``llm`` mantêm as credenciais reais.
    """
    if request.node.get_closest_marker("llm") is None:
        for name in CREDENTIAL_VARS:
            monkeypatch.setenv(name, "")


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def store_data() -> StoreData:
    return load_all(DATA_DIR)
