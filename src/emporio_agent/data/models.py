"""Modelos de dados da loja (contratos de ARCHITECTURE.md §5.2)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict

ProductStatus = Literal["active", "discontinued", "coming_soon"]
OrderStatus = Literal["pending", "confirmed", "shipped", "delivered", "cancelled"]

PRODUCT_STATUSES: frozenset[str] = frozenset(ProductStatus.__args__)
ORDER_STATUSES: frozenset[str] = frozenset(OrderStatus.__args__)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class Category(_Frozen):
    id: int
    name: str
    description: str


class Product(_Frozen):
    id: int
    name: str
    category_id: int
    category_name: str
    description: str
    price: Decimal
    stock: int
    status: ProductStatus
    specs: dict[str, str]
    created_at: date

    @property
    def available(self) -> bool:
        return self.status == "active" and self.stock > 0


class Promotion(_Frozen):
    id: int
    product_id: int
    discount_percent: int
    description: str
    is_active: bool


class OrderItem(_Frozen):
    product_id: int
    product_name: str
    quantity: int


class Order(_Frozen):
    id: int
    customer_id: int
    order_date: date
    status: OrderStatus
    total: Decimal
    payment_method: str
    tracking_code: str | None
    estimated_delivery: date | None
    notes: str | None
    items: list[OrderItem]


class Customer(_Frozen):
    id: int
    name: str
    phone_digits: str
    email: str
    city: str


ConflictKind = Literal["marca", "cordas", "teclas", "revisao_manual"]
ConflictDetection = Literal["automatica", "revisao_manual"]


class ProductConflict(_Frozen):
    """Divergência entre campos de um mesmo produto (DATA_ANALYSIS.md §3.1).

    Nenhum dos lados é tratado como verdadeiro: ambos os valores são expostos.
    """

    product_id: int
    kind: ConflictKind
    fields: tuple[str, ...]
    values: dict[str, str]
    detection: ConflictDetection
    note: str


@dataclass(frozen=True)
class StoreData:
    """Tabelas carregadas e normalizadas em memória (os CSVs não são alterados)."""

    products: pd.DataFrame
    categories: pd.DataFrame
    promotions: pd.DataFrame
    orders: pd.DataFrame
    order_items: pd.DataFrame
    customers: pd.DataFrame
    product_conflicts: dict[int, list[ProductConflict]]
