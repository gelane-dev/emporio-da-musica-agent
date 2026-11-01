"""Carregamento e normalização dos CSVs da loja.

Os arquivos são lidos como texto (sem inferência de tipos do pandas) e
convertidos explicitamente — preços como ``Decimal`` a partir do texto
original, para não introduzir erro de ponto flutuante. Nada é escrito em disco.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd

from emporio_agent.data.models import ORDER_STATUSES, PRODUCT_STATUSES, StoreData
from emporio_agent.data.quality import detect_product_conflicts

logger = logging.getLogger(__name__)

FILE_PREFIX = "desafio_tecnico_ai_eng - "

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "products": ("product_id", "price_brl", "name", "category_id", "description",
                 "stock_quantity", "status", "specs", "created_at"),
    "categories": ("category_id", "name", "description"),
    "promotions": ("promotion_id", "product_id", "discount_percent", "description", "is_active"),
    "orders": ("order_id", "customer_id", "order_date", "status", "total_brl",
               "payment_method", "tracking_code", "estimated_delivery", "notes"),
    "order_items": ("order_id", "quantity", "product_id"),
    "customers": ("customer_id", "name", "phone", "email", "city"),
}


class DataLoadError(Exception):
    """Falha ao carregar ou interpretar um CSV da loja."""


def csv_path(data_dir: Path, table: str) -> Path:
    return data_dir / f"{FILE_PREFIX}{table}.csv"


# --- conversores de célula -------------------------------------------------

def _int(value: str) -> int:
    return int(value)


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"valor monetário inválido: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"valor monetário inválido: {value!r}")
    return result


def _date(value: str) -> date:
    return date.fromisoformat(value)


def _optional(convert: Callable[[str], Any]) -> Callable[[str], Any]:
    def wrapper(value: str) -> Any:
        return None if value == "" else convert(value)

    return wrapper


def _optional_text(value: str) -> str | None:
    return value or None


def _bool01(value: str) -> bool:
    if value not in {"0", "1"}:
        raise ValueError(f"esperado 0 ou 1, recebido {value!r}")
    return value == "1"


def _one_of(allowed: frozenset[str]) -> Callable[[str], str]:
    def check(value: str) -> str:
        if value not in allowed:
            raise ValueError(f"valor {value!r} fora de {sorted(allowed)}")
        return value

    return check


def _specs(value: str) -> dict[str, str]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("specs deve ser um objeto JSON")
    return {str(k): str(v) for k, v in parsed.items()}


def normalize_phone(value: str) -> str:
    """Mantém só os dígitos: ``"(67) 99812-3456"`` → ``"67998123456"``."""
    return re.sub(r"\D", "", value)


def normalize_email(value: str) -> str:
    return "".join(value.split()).lower()


_CONVERTERS: dict[str, dict[str, Callable[[str], Any]]] = {
    "products": {
        "product_id": _int, "price_brl": _decimal, "category_id": _int,
        "stock_quantity": _int, "status": _one_of(PRODUCT_STATUSES),
        "specs": _specs, "created_at": _date,
    },
    "categories": {"category_id": _int},
    "promotions": {
        "promotion_id": _int, "product_id": _int, "discount_percent": _int,
        "is_active": _bool01,
    },
    "orders": {
        "order_id": _int, "customer_id": _int, "order_date": _date,
        "status": _one_of(ORDER_STATUSES), "total_brl": _decimal,
        "tracking_code": _optional_text, "estimated_delivery": _optional(_date),
        "notes": _optional_text,
    },
    "order_items": {"order_id": _int, "quantity": _int, "product_id": _int},
    "customers": {"customer_id": _int, "phone": normalize_phone, "email": normalize_email},
}


# --- leitura ------------------------------------------------------------------

def _read_table(data_dir: Path, table: str) -> pd.DataFrame:
    path = csv_path(data_dir, table)
    if not path.is_file():
        raise DataLoadError(f"Arquivo não encontrado: {path.name} (em {path.parent})")
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise DataLoadError(f"Não foi possível ler {path.name}: {exc}") from exc

    missing = [col for col in REQUIRED_COLUMNS[table] if col not in frame.columns]
    if missing:
        raise DataLoadError(f"{path.name}: coluna(s) ausente(s): {', '.join(missing)}")

    frame = frame[list(REQUIRED_COLUMNS[table])].copy()
    for column in frame.columns:
        frame[column] = frame[column].astype(object).map(str.strip)

    for column, convert in _CONVERTERS[table].items():
        converted: list[Any] = []
        for position, raw in enumerate(frame[column]):
            try:
                converted.append(convert(raw))
            except (ValueError, TypeError) as exc:
                line = position + 2  # +1 cabeçalho, +1 base 1
                raise DataLoadError(f"{path.name}, linha {line}, coluna {column!r}: {exc}") from exc
        dtype = "int64" if convert is _int else object
        frame[column] = pd.Series(converted, index=frame.index, dtype=dtype)
    return frame


def _join_category_name(products: pd.DataFrame, categories: pd.DataFrame) -> pd.DataFrame:
    names = dict(zip(categories["category_id"], categories["name"], strict=True))
    unknown = sorted(set(products["category_id"]) - set(names))
    if unknown:
        raise DataLoadError(f"products.csv: category_id sem categoria correspondente: {unknown}")
    products = products.copy()
    position = products.columns.get_loc("category_id") + 1
    products.insert(position, "category_name", products["category_id"].map(names).astype(object))
    return products


def load_all(data_dir: Path) -> StoreData:
    """Carrega os 6 CSVs de ``data_dir`` e detecta conflitos de cadastro."""
    tables = {table: _read_table(data_dir, table) for table in REQUIRED_COLUMNS}
    products = _join_category_name(tables["products"], tables["categories"])

    conflicts = detect_product_conflicts(products)
    for product_conflicts in conflicts.values():
        for conflict in product_conflicts:
            logger.warning(
                "Conflito de cadastro no produto #%d (%s, %s): %s %s",
                conflict.product_id, conflict.kind, conflict.detection,
                conflict.note, conflict.values,
            )

    return StoreData(
        products=products,
        categories=tables["categories"],
        promotions=tables["promotions"],
        orders=tables["orders"],
        order_items=tables["order_items"],
        customers=tables["customers"].rename(columns={"phone": "phone_digits"}),
        product_conflicts=conflicts,
    )
