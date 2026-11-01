"""Testes da T03: repositórios de catálogo e pedidos."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pandas as pd
import pytest

from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.domain.text import compact, normalize, stem, tokens

VIOLOES_ATE_1000 = [81, 82, 83, 84, 85, 86, 87, 88, 89, 91, 107, 112]


@pytest.fixture(scope="module")
def catalog(store_data):
    return CatalogRepository(store_data)


@pytest.fixture(scope="module")
def orders(store_data):
    return OrderRepository(store_data)


# --- texto ------------------------------------------------------------------

def test_text_normalization():
    assert normalize("Violão  Elétrico-Aço!") == "violao eletrico aco"
    assert compact("Takamine GD-20") == "takaminegd20"
    assert stem("violoes") == "violao"
    assert stem("guitarras") == "guitarra"
    assert stem("baixo") == "baixo"
    assert tokens("Quais violões para iniciantes?") == ["violao", "iniciante"]


# --- busca filtrada ---------------------------------------------------------

def test_search_violoes_up_to_1000(catalog):
    found = catalog.search(category_id=5, max_price=Decimal("1000"), limit=50)
    assert sorted(p.id for p in found) == VIOLOES_ATE_1000
    assert 96 not in {p.id for p in found} and 113 not in {p.id for p in found}


def test_search_only_available_never_returns_unavailable(catalog):
    found = catalog.search(only_available=True, limit=100)
    assert found
    assert all(p.status == "active" and p.stock > 0 for p in found)
    assert {96, 113, 130, 136}.isdisjoint(p.id for p in found)


def test_search_can_include_unavailable(catalog):
    found = catalog.search(only_available=False, limit=100)
    assert len(found) == 65


def test_search_price_bounds_are_inclusive(catalog):
    found = catalog.search(min_price=Decimal("599.9"), max_price=Decimal("599.9"), limit=10)
    assert [p.id for p in found] == [81]


def test_search_sort_by_price(catalog):
    asc = catalog.search(category_id=5, max_price=Decimal("1000"), sort="preco_asc", limit=50)
    assert [p.price for p in asc] == sorted(p.price for p in asc)
    desc = catalog.search(category_id=5, max_price=Decimal("1000"), sort="preco_desc", limit=50)
    assert [p.price for p in desc] == sorted((p.price for p in desc), reverse=True)
    assert desc[0].id == 112 and asc[0].id == 83


def test_search_limit(catalog):
    assert len(catalog.search(limit=3)) == 3
    assert catalog.search(limit=0) == []


def test_search_by_text_requires_all_terms(catalog):
    found = catalog.search(text="dreadnought", limit=50)
    assert found and all("dreadnought" in p.name.lower() or "dreadnought" in p.description.lower() for p in found)

    nylon_eletrico = catalog.search(text="violão elétrico nylon", limit=50)
    assert {98, 99, 100, 101, 102, 115}.issubset({p.id for p in nylon_eletrico})
    assert all(p.category_id == 5 for p in nylon_eletrico)


def test_search_by_text_tolerates_accents_plural_and_typos(catalog):
    assert {p.id for p in catalog.search(text="ukuleles tenor", limit=50)} >= {124, 125, 126, 127}
    assert 84 in {p.id for p in catalog.search(text="cedro", limit=50)}
    assert 95 in {p.id for p in catalog.search(text="takamini", limit=50)}


def test_search_by_text_without_match_is_empty(catalog):
    assert catalog.search(text="saxofone", limit=50) == []


# --- busca por nome ---------------------------------------------------------

@pytest.mark.parametrize("query", ["takamine gd20", "Takamine GD-20", "takamine gd 20", "TAKAMINE GD20"])
def test_find_by_name_takamine(catalog, query):
    (best, score), *_ = catalog.find_by_name(query)
    assert best.id == 95
    assert score == 100


def test_find_by_name_ambiguous_returns_multiple_candidates(catalog):
    results = catalog.find_by_name("violao yamaha", limit=5)
    assert len(results) >= 2
    assert all("Yamaha" in p.name for p, _ in results)
    assert results[0][1] == results[1][1]  # empate: a tool decidirá por AMBIGUOUS


def test_find_by_name_without_match(catalog):
    assert catalog.find_by_name("xyz qualquer coisa") == []
    assert catalog.find_by_name("") == []


def test_find_by_name_includes_any_status(catalog):
    # A decisão de oferecer ou não é da tool; o repositório encontra o produto.
    assert catalog.find_by_name("Shelby SN-7C")[0][0].id == 113


# --- promoções --------------------------------------------------------------

def test_active_promotions(catalog):
    assert [(p.discount_percent, p.description) for p in catalog.active_promotions(121)] == [
        (20, "Desconto Exclusivo")
    ]
    assert catalog.active_promotions(95) == []


def test_inactive_promotions(catalog):
    assert [(p.discount_percent, p.description) for p in catalog.inactive_promotions(95)] == [
        (12, "Oferta Especial")
    ]
    assert len(catalog.inactive_promotions(96)) == 2  # sem datas: todas são devolvidas
    assert catalog.inactive_promotions(81) == []


def test_multiple_active_promotions_are_all_returned(store_data):
    extra = pd.DataFrame(
        [{"promotion_id": 99, "product_id": 121, "discount_percent": 5,
          "description": "Sintética", "is_active": True}]
    )
    data = dataclasses.replace(store_data, promotions=pd.concat([store_data.promotions, extra], ignore_index=True))
    promotions = CatalogRepository(data).active_promotions(121)
    assert [p.discount_percent for p in promotions] == [20, 5]  # nenhuma escolhida


# --- conflitos, similares, categorias ---------------------------------------

def test_conflicts(catalog):
    assert [c.kind for c in catalog.conflicts(142)] == ["marca", "teclas"]
    assert catalog.conflicts(95) == []


def test_similar_for_out_of_stock_product(catalog):
    product = catalog.get(96)
    suggestions = catalog.similar(product)
    assert len(suggestions) == 3
    assert all(p.category_id == 5 and p.available and p.id != 96 for p in suggestions)
    distances = [abs(p.price - product.price) for p in suggestions]
    assert distances == sorted(distances)
    assert suggestions[0].id == 107  # R$ 799,00, o mais próximo de R$ 799,90


def test_categories_with_available_counts(catalog):
    counts = {category.name: count for category, count in catalog.categories()}
    assert len(counts) == 9
    assert counts["Instrumentos de Sopro (Madeiras)"] == 0
    assert counts["Instrumentos de Sopro (Metais)"] == 0
    assert counts["Cordas Orquestrais"] == 0
    assert counts["Violões"] == 33  # 35 menos #96 (sem estoque) e #113 (descontinuado)
    assert counts["Baixos"] == 3  # #136 descontinuado não conta


def test_get_product(catalog):
    product = catalog.get(95)
    assert product.name == "Takamine GD20 Dreadnought Natural"
    assert product.price == Decimal("2199")
    assert product.available
    assert catalog.get(999) is None


# --- pedidos ----------------------------------------------------------------

def test_order_with_two_items(orders):
    order = orders.get(15)
    assert [(i.product_id, i.product_name, i.quantity) for i in order.items] == [
        (82, "Yamaha C70 Nylon Natural", 1),
        (106, "Taylor 214ce Elétrico Aço Natural", 1),
    ]
    assert order.total == Decimal("8348")


def test_missing_order(orders):
    assert orders.get(999) is None


def test_customer_of_order(orders):
    customer = orders.customer_of(orders.get(8))
    assert customer.id == 2
    assert customer.phone_digits == "67996547821"
