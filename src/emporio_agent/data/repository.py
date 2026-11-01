"""Consultas sobre catálogo e pedidos (contratos de ARCHITECTURE.md §5.2).

O repositório só lê dados já carregados; não aplica regras de negócio
(preço final, parcelas, frete) nem decide entre informações conflitantes.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Literal

from rapidfuzz import fuzz

from emporio_agent.data.models import (
    Category,
    Customer,
    Order,
    OrderItem,
    Product,
    ProductConflict,
    Promotion,
    StoreData,
)
from emporio_agent.domain.text import compact, tokens

SortOrder = Literal["preco_asc", "preco_desc", "relevancia"]

NAME_MATCH_MIN_SCORE = 70.0
"""Nota mínima (0–100) para um produto aparecer em ``find_by_name``."""

TOKEN_MATCH_MIN_SCORE = 85.0
"""Nota mínima para um termo da busca casar com um termo do produto (tolera erros de digitação)."""


def _token_score(query_token: str, product_tokens: set[str]) -> float:
    if query_token in product_tokens:
        return 100.0
    best = 0.0
    for token in product_tokens:
        if len(query_token) >= 3 and len(token) >= 3 and (
            token.startswith(query_token) or query_token.startswith(token)
        ):
            return 100.0
        best = max(best, fuzz.ratio(query_token, token))
    return best


class CatalogRepository:
    def __init__(self, data: StoreData):
        self._categories: dict[int, Category] = {
            row.category_id: Category(id=row.category_id, name=row.name, description=row.description)
            for row in data.categories.itertuples(index=False)
        }
        self._products: dict[int, Product] = {
            row.product_id: Product(
                id=row.product_id,
                name=row.name,
                category_id=row.category_id,
                category_name=row.category_name,
                description=row.description,
                price=row.price_brl,
                stock=row.stock_quantity,
                status=row.status,
                specs=row.specs,
                created_at=row.created_at,
            )
            for row in data.products.itertuples(index=False)
        }
        self._promotions: dict[int, list[Promotion]] = defaultdict(list)
        for row in data.promotions.itertuples(index=False):
            self._promotions[row.product_id].append(
                Promotion(
                    id=row.promotion_id,
                    product_id=row.product_id,
                    discount_percent=row.discount_percent,
                    description=row.description,
                    is_active=row.is_active,
                )
            )
        self._conflicts = data.product_conflicts

        # Índices de busca (calculados uma vez).
        self._search_tokens: dict[int, set[str]] = {
            pid: set(
                tokens(
                    " ".join([p.name, p.category_name, p.description, *p.specs.values()]),
                    drop_stopwords=False,
                )
            )
            for pid, p in self._products.items()
        }
        self._name_text: dict[int, str] = {
            pid: " ".join(tokens(f"{p.name} {p.category_name}", drop_stopwords=False))
            for pid, p in self._products.items()
        }
        self._name_compact: dict[int, str] = {pid: compact(p.name) for pid, p in self._products.items()}

    # --- produtos -------------------------------------------------------------

    def get(self, product_id: int) -> Product | None:
        return self._products.get(product_id)

    def search(
        self,
        *,
        text: str | None = None,
        category_id: int | None = None,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        only_available: bool = True,
        limit: int = 10,
        sort: SortOrder = "relevancia",
    ) -> list[Product]:
        """Filtra o catálogo. Com ``text``, todos os termos relevantes precisam casar.

        Os preços filtrados são os de tabela; preço promocional é responsabilidade do domínio.
        """
        query_tokens = tokens(text) if text else []
        scored: list[tuple[float, Product]] = []
        for product in self._products.values():
            if only_available and not product.available:
                continue
            if category_id is not None and product.category_id != category_id:
                continue
            if min_price is not None and product.price < min_price:
                continue
            if max_price is not None and product.price > max_price:
                continue
            relevance = 0.0
            if query_tokens:
                scores = [_token_score(t, self._search_tokens[product.id]) for t in query_tokens]
                if min(scores) < TOKEN_MATCH_MIN_SCORE:
                    continue
                relevance = sum(scores) / len(scores)
            scored.append((relevance, product))

        if sort == "preco_asc":
            scored.sort(key=lambda item: (item[1].price, item[1].id))
        elif sort == "preco_desc":
            scored.sort(key=lambda item: (-item[1].price, item[1].id))
        else:
            scored.sort(key=lambda item: (-item[0], item[1].id))
        return [product for _, product in scored[: max(limit, 0)]]

    def find_by_name(
        self, query: str, limit: int = 3, min_score: float = NAME_MATCH_MIN_SCORE
    ) -> list[tuple[Product, float]]:
        """Produtos cujo nome (e categoria) se parecem com ``query``, por nota decrescente.

        Considera produtos em qualquer status: quem decide o que oferecer é a camada de tools.
        """
        normalized_query = " ".join(tokens(query))
        compact_query = compact(query)
        if not normalized_query and not compact_query:
            return []
        results: list[tuple[Product, float]] = []
        for pid, product in self._products.items():
            score = fuzz.token_set_ratio(normalized_query, self._name_text[pid])
            if len(compact_query) >= 4:
                score = max(score, fuzz.partial_ratio(compact_query, self._name_compact[pid]))
            if score >= min_score:
                results.append((product, float(score)))
        results.sort(key=lambda item: (-item[1], item[0].id))
        return results[:limit]

    def similar(self, product: Product, limit: int = 3) -> list[Product]:
        """Sugestões: mesma categoria, disponíveis, ordenadas pela proximidade de preço.

        Heurística de recomendação (política 7.3), não regra de negócio.
        """
        candidates = [
            p
            for p in self._products.values()
            if p.id != product.id and p.category_id == product.category_id and p.available
        ]
        candidates.sort(key=lambda p: (abs(p.price - product.price), p.id))
        return candidates[:limit]

    # --- categorias, promoções e conflitos -------------------------------------

    def categories(self) -> list[tuple[Category, int]]:
        available = defaultdict(int)
        for product in self._products.values():
            if product.available:
                available[product.category_id] += 1
        return [(category, available[cid]) for cid, category in sorted(self._categories.items())]

    def active_promotions(self, product_id: int) -> list[Promotion]:
        """Todas as promoções ativas do produto, sem escolher entre elas (DATA_ANALYSIS P15)."""
        return sorted((p for p in self._promotions.get(product_id, []) if p.is_active), key=lambda p: p.id)

    def inactive_promotions(self, product_id: int) -> list[Promotion]:
        """Promoções encerradas do produto. Sem datas nos dados, não há como saber qual é a mais recente."""
        return sorted((p for p in self._promotions.get(product_id, []) if not p.is_active), key=lambda p: p.id)

    def conflicts(self, product_id: int) -> list[ProductConflict]:
        return list(self._conflicts.get(product_id, []))


class OrderRepository:
    def __init__(self, data: StoreData):
        product_names = dict(zip(data.products["product_id"], data.products["name"], strict=True))
        items: dict[int, list[OrderItem]] = defaultdict(list)
        for row in data.order_items.itertuples(index=False):
            items[row.order_id].append(
                OrderItem(
                    product_id=row.product_id,
                    product_name=product_names.get(row.product_id, f"Produto #{row.product_id}"),
                    quantity=row.quantity,
                )
            )
        self._orders: dict[int, Order] = {
            row.order_id: Order(
                id=row.order_id,
                customer_id=row.customer_id,
                order_date=row.order_date,
                status=row.status,
                total=row.total_brl,
                payment_method=row.payment_method,
                tracking_code=row.tracking_code,
                estimated_delivery=row.estimated_delivery,
                notes=row.notes,
                items=items.get(row.order_id, []),
            )
            for row in data.orders.itertuples(index=False)
        }
        self._customers: dict[int, Customer] = {
            row.customer_id: Customer(
                id=row.customer_id,
                name=row.name,
                phone_digits=row.phone_digits,
                email=row.email,
                city=row.city,
            )
            for row in data.customers.itertuples(index=False)
        }

    def get(self, order_id: int) -> Order | None:
        return self._orders.get(order_id)

    def customer_of(self, order: Order) -> Customer:
        """Cliente dono do pedido. Lança ``KeyError`` se o cadastro estiver inconsistente."""
        return self._customers[order.customer_id]
