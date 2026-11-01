"""Testes da T04: preço promocional, PIX, parcelamento e pagamento combinado."""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from emporio_agent.data.models import Promotion
from emporio_agent.data.repository import CatalogRepository
from emporio_agent.domain import pricing
from emporio_agent.domain.pricing import (
    LIMITATION_P3,
    LIMITATION_P4,
    LIMITATION_P12,
    LIMITATION_P15,
    combined_payment_status,
    format_brl,
    installment_options,
    quote,
)

D = Decimal


def promo(pid: int, percent: int, active: bool = True) -> Promotion:
    return Promotion(id=pid, product_id=1, discount_percent=percent, description=f"Promo {pid}", is_active=active)


def by_n(options):
    return {o.n: (o.value, o.status) for o in options}


@pytest.fixture(scope="module")
def catalog(store_data):
    return CatalogRepository(store_data)


# --- produtos reais -----------------------------------------------------------

def test_takamine_gd20_without_promotion(catalog):
    product = catalog.get(95)
    q = quote(product.price, catalog.active_promotions(95))
    assert q.list_price == q.final_price == D("2199")
    assert q.promo is None
    assert q.pix_price == D("2089.05")
    assert [o.n for o in q.installments] == list(range(1, 13))
    assert all(o.status == "confirmada" for o in q.installments)
    assert q.max_confirmed_installments == 12
    assert by_n(q.installments)[12] == (D("183.25"), "confirmada")
    assert q.combined_payment == "permitido"
    assert q.limitations == []


def test_ohana_ck20_with_active_promotion(catalog):
    product = catalog.get(121)
    q = quote(product.price, catalog.active_promotions(121))
    assert q.list_price == D("549")
    assert q.promo.percent == 20 and q.promo.description == "Desconto Exclusivo"
    assert q.final_price == q.promo.price == D("439.20")
    assert q.pix_price is None  # PIX não incide sobre preço promocional
    options = by_n(q.installments)
    assert [n for n, (_, s) in options.items() if s == "confirmada"] == [1, 2, 3, 4]
    assert options[4] == (D("109.80"), "confirmada")
    assert options[5] == (D("87.84"), "a_confirmar")
    assert set(options) == {1, 2, 3, 4, 5}  # 6x–12x omitidas
    assert q.max_confirmed_installments == 4
    assert q.limitations == [LIMITATION_P3]
    assert q.limitations[0].code == "MANUAL_CONTRADITORIO"
    assert "seções 3 e 3.1" in q.limitations[0].source
    assert q.combined_payment == "nao_permitido"


# --- parcelamento -----------------------------------------------------------

def test_159_90_short_installments_pending():
    q = quote(D("159.90"), [])
    options = by_n(q.installments)
    assert options == {
        1: (D("159.90"), "confirmada"),
        2: (D("79.95"), "a_confirmar"),
        3: (D("53.30"), "a_confirmar"),
    }
    assert q.max_confirmed_installments == 1
    assert q.limitations == [LIMITATION_P4]


def test_90_has_no_confirmed_installment():
    q = quote(D("90"), [])
    assert by_n(q.installments)[1] == (D("90.00"), "a_confirmar")
    assert q.max_confirmed_installments is None
    assert LIMITATION_P4 in q.limitations


def test_installment_of_exactly_100_is_confirmed():
    assert by_n(installment_options(D("1200")))[12] == (D("100.00"), "confirmada")


def test_comparison_uses_exact_value_not_rounded():
    # 1.199,99 / 12 = 99,999… → arredondaria para 100,00, mas não atinge o mínimo.
    assert 12 not in by_n(installment_options(D("1199.99")))


def test_500_mid_tier():
    options = by_n(installment_options(D("500")))
    assert options[5] == (D("100.00"), "confirmada")
    assert options[6] == (D("83.33"), "a_confirmar")
    assert 7 not in options


def test_never_more_than_12_installments():
    # Mesmo com parcela muito acima de R$ 100, o limite do manual é 12x.
    options = installment_options(D("19567"))
    assert max(o.n for o in options) == pricing.MAX_INSTALLMENTS == 12
    assert by_n(options)[12] == (D("1630.58"), "confirmada")
    q = quote(D("19567"), [])
    assert q.max_confirmed_installments == 12
    for amount in ["0.01", "50", "1000", "99999.99"]:
        assert all(1 <= o.n <= 12 for o in installment_options(D(amount)))


def test_no_minimum_of_50_is_applied():
    # A leitura "mínimo de R$ 50 até 3x" não é uma regra confirmada (P4).
    options = by_n(installment_options(D("120")))
    assert options[3] == (D("40.00"), "a_confirmar")
    assert options[2] == (D("60.00"), "a_confirmar")
    # Abaixo de R$ 80 de 4x a 6x é vedado pelas duas fontes, independentemente de R$ 50.
    assert 4 not in options


def test_limitations_match_pending_ranges():
    # P4 (até 3x) e P3 (4x–6x) nunca coexistem: 3x < R$ 100 implica 5x < R$ 60.
    q = quote(D("270"), [])  # 3x = 90 (P4), 4x = 67,50 (omitida), 2x = 135
    assert by_n(q.installments)[3][1] == "a_confirmar"
    assert q.limitations == [LIMITATION_P4]
    q = quote(D("250"), [])  # 2x = 125, 3x = 83,33 (P4)
    assert LIMITATION_P4 in q.limitations
    q = quote(D("480"), [])  # 5x = 96 (P3), 6x = 80 (P3), 4x = 120
    assert q.limitations == [LIMITATION_P3]
    assert by_n(q.installments)[6] == (D("80.00"), "a_confirmar")


# --- pagamento combinado ------------------------------------------------------

@pytest.mark.parametrize(
    ("amount", "expected"),
    [("1999.99", "nao_permitido"), ("2000", "a_confirmar"), ("2000.00", "a_confirmar"), ("2000.01", "permitido")],
)
def test_combined_payment_strictly_above_2000(amount, expected):
    assert combined_payment_status(D(amount)) == expected


def test_combined_payment_at_exactly_2000_returns_explicit_limitation():
    q = quote(D("2000"), [])
    assert q.combined_payment == "a_confirmar"
    assert LIMITATION_P12 in q.limitations
    assert LIMITATION_P12.code == "MANUAL_OMISSO"
    assert "R$ 2.000,00" in LIMITATION_P12.message


def test_combined_payment_uses_promotional_price():
    # 2.400 com 20% = 1.920 → não permitido, pois o valor da compra fica abaixo do limite.
    assert quote(D("2400"), [promo(1, 20)]).combined_payment == "nao_permitido"


# --- promoções ----------------------------------------------------------------

def test_multiple_active_promotions_pick_none():
    q = quote(D("549"), [promo(1, 20), promo(2, 5)])
    assert q.promo is None
    assert q.final_price == q.list_price == D("549")
    assert q.pix_price is None
    assert LIMITATION_P15 in q.limitations
    assert LIMITATION_P15.code == "MANUAL_OMISSO"


def test_inactive_promotion_is_rejected():
    with pytest.raises(ValueError, match="não está ativa"):
        quote(D("549"), [promo(1, 20, active=False)])


@pytest.mark.parametrize("percent", [0, 100, -5])
def test_invalid_discount_is_rejected(percent):
    with pytest.raises(ValueError, match="desconto inválido"):
        quote(D("549"), [promo(1, percent)])


@pytest.mark.parametrize("amount", [D("0"), D("-1"), D("NaN"), 100.0])
def test_invalid_amount_is_rejected(amount):
    with pytest.raises(ValueError):
        installment_options(amount)


# --- formatação e arredondamento ---------------------------------------------------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (D("2089.05"), "R$ 2.089,05"),
        (D("11499"), "R$ 11.499,00"),
        (D("159.9"), "R$ 159,90"),
        (D("0.5"), "R$ 0,50"),
        (D("1234567.891"), "R$ 1.234.567,89"),
        (D("0.005"), "R$ 0,01"),  # ROUND_HALF_UP
    ],
)
def test_format_brl(value, expected):
    assert format_brl(value) == expected


def test_all_values_are_decimal():
    q = quote(D("549"), [promo(1, 20)])
    assert all(isinstance(v, Decimal) for v in (q.list_price, q.final_price, q.promo.price))
    assert all(isinstance(o.value, Decimal) for o in q.installments)


def test_domain_does_not_import_data_layer():
    source = Path(pricing.__file__).read_text(encoding="utf-8")
    imported = {
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(module.startswith("emporio_agent.data") for module in imported)
