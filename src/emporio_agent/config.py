"""Configuração da aplicação.

Os valores vêm de variáveis de ambiente, opcionalmente definidas em um arquivo
``.env`` na raiz do repositório. Variáveis já presentes no ambiente têm
prioridade sobre o ``.env``.

Variáveis suportadas (todas opcionais):

- ``LLM_PROVIDER``: provedor do modelo (padrão ``anthropic``).
- ``LLM_MODEL``: identificador do modelo (padrão ``claude-sonnet-5-5``).
- ``LLM_MAX_TOKENS``: máximo de tokens por resposta (padrão ``1024``).
- ``REFERENCE_DATE``: data/hora controlada para testes e exemplos, em ISO 8601
  (``2026-03-25`` ou ``2026-03-25T10:30``). Sem fuso explícito, é interpretada
  no fuso da loja; só data equivale a 00:00. Ausente ou vazia ⇒ hora real.
- ``MAX_TOOL_ITERATIONS``: limite de chamadas de ferramenta por mensagem (padrão ``6``).
- ``MAX_HISTORY_TURNS``: turnos de histórico enviados ao modelo (padrão ``20``).

A chave de API não faz parte de ``Settings``: é lida pelo adaptador do
provedor (T08), para que cada provedor use sua própria variável.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
STORE_TIMEZONE = "America/Campo_Grande"


class Settings(BaseModel):
    """Configuração imutável da aplicação."""

    model_config = ConfigDict(frozen=True)

    data_dir: Path = REPO_ROOT / "data"
    policies_path: Path = REPO_ROOT / "knowledge" / "policies.md"
    runtime_dir: Path = REPO_ROOT / "runtime"
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = Field(default=1024, gt=0)
    timezone: str = STORE_TIMEZONE
    reference_datetime: datetime | None = None
    max_tool_iterations: int = Field(default=6, gt=0)
    max_history_turns: int = Field(default=20, gt=0)

    @field_validator("llm_provider", "llm_model")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("não pode ser vazio")
        return value

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        ZoneInfo(value)  # lança ZoneInfoNotFoundError se o fuso não existir
        return value

    @field_validator("reference_datetime")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("reference_datetime precisa ter fuso horário")
        return value


def parse_reference_date(raw: str, timezone: str = STORE_TIMEZONE) -> datetime:
    """Converte ``REFERENCE_DATE`` em ``datetime`` com fuso.

    Aceita data (``YYYY-MM-DD``, equivale a 00:00) ou data e hora ISO 8601.
    Sem fuso explícito, usa o fuso da loja.
    """
    raw = raw.strip()
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(
            f"REFERENCE_DATE inválida: {raw!r}. Use ISO 8601, ex.: 2026-03-25 ou 2026-03-25T10:30"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(timezone))
    return parsed


def load_settings(
    env_file: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Settings:
    """Monta ``Settings`` a partir do ``.env`` e do ambiente.

    ``env_file`` padrão: ``<repo>/.env`` (ignorado se não existir).
    ``environ`` padrão: ``os.environ``; tem prioridade sobre o ``.env``.
    """
    env_path = env_file if env_file is not None else REPO_ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.is_file():
        values.update({k: v for k, v in dotenv_values(env_path).items() if v is not None})
    values.update(os.environ if environ is None else environ)

    kwargs: dict[str, object] = {}
    mapping = {
        "LLM_PROVIDER": "llm_provider",
        "LLM_MODEL": "llm_model",
        "LLM_MAX_TOKENS": "llm_max_tokens",
        "MAX_TOOL_ITERATIONS": "max_tool_iterations",
        "MAX_HISTORY_TURNS": "max_history_turns",
    }
    for env_name, field in mapping.items():
        raw = values.get(env_name, "").strip()
        if raw:
            kwargs[field] = raw

    raw_reference = values.get("REFERENCE_DATE", "").strip()
    if raw_reference:
        kwargs["reference_datetime"] = parse_reference_date(raw_reference)

    return Settings(**kwargs)


def now(settings: Settings) -> datetime:
    """Data/hora de referência com fuso da loja.

    Usa ``settings.reference_datetime`` quando definido (testes e exemplos);
    caso contrário, o relógio real do sistema.
    """
    tz = ZoneInfo(settings.timezone)
    if settings.reference_datetime is not None:
        return settings.reference_datetime.astimezone(tz)
    return datetime.now(tz)
