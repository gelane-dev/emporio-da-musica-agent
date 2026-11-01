"""Testes da T01: configuração, data de referência e ponto de entrada."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from emporio_agent import __version__
from emporio_agent.config import REPO_ROOT, Settings, load_settings, now, parse_reference_date

TZ = ZoneInfo("America/Campo_Grande")
MISSING_ENV_FILE = Path("nao-existe.env")


def test_defaults_without_env():
    settings = load_settings(env_file=MISSING_ENV_FILE, environ={})
    assert settings.llm_provider == "groq"
    assert settings.llm_model == "openai/gpt-oss-120b"
    assert settings.reference_datetime is None
    assert settings.data_dir == REPO_ROOT / "data"
    assert settings.timezone == "America/Campo_Grande"


def test_reads_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_PROVIDER=outro\nLLM_MODEL=modelo-x\nLLM_MAX_TOKENS=512\nREFERENCE_DATE=2026-03-25T10:30\n",
        encoding="utf-8",
    )
    settings = load_settings(env_file=env_file, environ={})
    assert settings.llm_provider == "outro"
    assert settings.llm_model == "modelo-x"
    assert settings.llm_max_tokens == 512
    assert settings.reference_datetime == datetime(2026, 3, 25, 10, 30, tzinfo=TZ)


def test_environment_overrides_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=do-arquivo\n", encoding="utf-8")
    settings = load_settings(env_file=env_file, environ={"LLM_MODEL": "do-ambiente"})
    assert settings.llm_model == "do-ambiente"


def test_blank_reference_date_means_real_clock():
    settings = load_settings(env_file=MISSING_ENV_FILE, environ={"REFERENCE_DATE": "  "})
    assert settings.reference_datetime is None


def test_now_without_reference_is_current_time_in_store_timezone():
    settings = load_settings(env_file=MISSING_ENV_FILE, environ={})
    current = now(settings)
    assert current.tzinfo is not None
    assert current.utcoffset() == datetime.now(TZ).utcoffset()
    assert abs(current - datetime.now(TZ)) < timedelta(seconds=5)


def test_now_with_reference_is_fixed_and_aware():
    settings = load_settings(env_file=MISSING_ENV_FILE, environ={"REFERENCE_DATE": "2026-03-25T10:30"})
    first, second = now(settings), now(settings)
    assert first == second == datetime(2026, 3, 25, 10, 30, tzinfo=TZ)
    assert first.tzinfo is not None


def test_reference_date_only_is_midnight():
    assert parse_reference_date("2026-03-25") == datetime(2026, 3, 25, 0, 0, tzinfo=TZ)


def test_reference_date_with_explicit_offset_is_converted_to_store_timezone():
    settings = load_settings(
        env_file=MISSING_ENV_FILE, environ={"REFERENCE_DATE": "2026-03-25T14:00+00:00"}
    )
    assert now(settings) == datetime(2026, 3, 25, 10, 0, tzinfo=TZ)  # UTC-4


def test_invalid_reference_date_raises_clear_error():
    with pytest.raises(ValueError, match="REFERENCE_DATE inválida"):
        load_settings(env_file=MISSING_ENV_FILE, environ={"REFERENCE_DATE": "25/03/2026"})


def test_naive_reference_datetime_rejected():
    with pytest.raises(ValueError):
        Settings(reference_datetime=datetime(2026, 3, 25))


def test_main_module_runs():
    result = subprocess.run(
        [sys.executable, "-m", "emporio_agent", "--version"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        check=True,
    )
    assert __version__ in result.stdout
