"""Fixtures compartilhadas."""

from __future__ import annotations

from pathlib import Path

import pytest

from emporio_agent.config import REPO_ROOT
from emporio_agent.data.loader import load_all
from emporio_agent.data.models import StoreData

DATA_DIR: Path = REPO_ROOT / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def store_data() -> StoreData:
    return load_all(DATA_DIR)
