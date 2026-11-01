"""Testes da T05 (frete): contrato em ARCHITECTURE §5.3.1, manual seções 5.1 e 5.2."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from emporio_agent.domain import shipping
from emporio_agent.domain.shipping import (
    FREE_SHIPPING_THRESHOLD,
    LIMITATION_CIDADE_NAO_INFORMADA,
    LIMITATION_P5,
    LIMITATION_P8,
    LIMITATION_VALOR_POR_CEP,
    METRO_DEADLINE,
    METRO_FIXED_FEE,
    NOTE_FRETE_ESPECIAL,
    NOTE_MOTOBOY,
    NOTE_SEGURO,
    OTHER_CITIES_DEADLINES,
    is_campo_grande,
    shipping_estimate,
)

D = Decimal

CAMPO_GRANDE_VARIANTS = [
    "Campo Grande",
    "campo grande",
    "CAMPO GRANDE",
    "Campo Grande - MS",
    "Campo Grande/MS",
    "campo grande-ms",
    "  Campo   Grande  ",
    "\tCampo Grande\n",
]


# --- constantes literais -------------------------------------------------------------

def test_constants_match_manual():
    assert FREE_SHIPPING_THRESHOLD == D("500.00")
    assert METRO_FIXED_FEE == D("35.00")
    assert METRO_DEADLINE == "1 a 3 dias úteis"
    assert OTHER_CITIES_DEADLINES == (
        "PAC (Correios): 5 a 12 dias úteis",
        "SEDEX (Correios): 2 a 5 dias úteis",
        "Jadlog (.package): 3 a 8 dias úteis",
    )
    assert NOTE_MOTOBOY == (
        "Entrega realizada por motoboy próprio. O cliente será contactado por telefone antes da entrega."
    )
    assert NOTE_SEGURO == "Todos os envios incluem seguro contra extravios e danos durante o transporte."
    assert NOTE_FRETE_ESPECIAL == (
        "Instrumentos de grande porte (baterias acústicas, pianos digitais, contrabaixos) "
        "podem exigir frete especial com cotação individual."
    )


def test_limitation_codes_and_keywords():
    assert LIMITATION_P5.code == "MANUAL_OMISSO"
    assert LIMITATION_P8.code == "MANUAL_OMISSO"
    assert LIMITATION_VALOR_POR_CEP.code == "DADO_NAO_REGISTRADO"
    assert LIMITATION_CIDADE_NAO_INFORMADA.code == "DADO_NAO_REGISTRADO"
    assert "500,00" in LIMITATION_P5.message
    p8 = LIMITATION_P8.message
    assert "500,00" in p8 and "35,00" in p8 and "1 a 3 dias úteis" in p8
    assert "cep" in LIMITATION_VALOR_POR_CEP.message.lower()
    assert "cidade" in LIMITATION_CIDADE_NAO_INFORMADA.message.lower()


# --- is_campo_grande ---------------------------------------------------------------------

@pytest.mark.parametrize("city", CAMPO_GRANDE_VARIANTS)
def test_is_campo_grande_variants(city):
    assert is_campo_grande(city) is True


@pytest.mark.parametrize(
    "city",
    ["Dourados", "Três Lagoas", "Campo Grandeza", "Campo Grande do Sul", "Campo", "Grande", "São Paulo", "", "   "],
)
def test_is_campo_grande_rejects_others(city):
    assert is_campo_grande(city) is False


# --- tabela: Campo Grande ------------------------------------------------------------------

def test_campo_grande_above_threshold_free():
    e = shipping_estimate("Campo Grande", D("500.01"))
    assert e.region == "metropolitana"
    assert e.fee_status == "gratis"
    assert e.fee == D("0.00")
    assert isinstance(e.fee, Decimal)
    assert e.deadlines == [METRO_DEADLINE]
    assert e.notes == [NOTE_MOTOBOY]
    assert e.limitations == []


def test_campo_grande_below_threshold_fixed_fee():
    e = shipping_estimate("Campo Grande", D("499.99"))
    assert e.region == "metropolitana"
    assert e.fee_status == "taxa_fixa"
    assert e.fee == D("35.00")
    assert isinstance(e.fee, Decimal)
    assert e.deadlines == [METRO_DEADLINE]
    assert e.notes == [NOTE_MOTOBOY]
    assert e.limitations == []


def test_campo_grande_exactly_threshold_p5():
    e = shipping_estimate("Campo Grande", D("500.00"))
    assert e.region == "metropolitana"
    assert e.fee_status == "nao_disponivel"
    assert e.fee is None
    assert e.deadlines == [METRO_DEADLINE]
    assert e.notes == [NOTE_MOTOBOY]
    assert e.limitations == [LIMITATION_P5]
    assert e.limitations[0] is LIMITATION_P5


@pytest.mark.parametrize("value", [D("500"), D("500.0"), D("500.000")])
def test_threshold_equality_ignores_decimal_scale(value):
    e = shipping_estimate("Campo Grande", value)
    assert e.fee_status == "nao_disponivel"
    assert e.fee is None
    assert e.limitations == [LIMITATION_P5]


@pytest.mark.parametrize("city", CAMPO_GRANDE_VARIANTS)
def test_variants_get_metro_rules(city):
    assert shipping_estimate(city, D("600")).fee_status == "gratis"
    assert shipping_estimate(city, D("100")).fee == D("35.00")
    assert shipping_estimate(city, D("500")).limitations == [LIMITATION_P5]
    assert shipping_estimate(city, D("600")).region == "metropolitana"


@pytest.mark.parametrize("value", [D("0.01"), D("1"), D("499.99")])
def test_campo_grande_small_values_fixed_fee(value):
    e = shipping_estimate("Campo Grande", value)
    assert e.fee_status == "taxa_fixa"
    assert e.fee == D("35.00")


def test_campo_grande_large_value_free():
    e = shipping_estimate("Campo Grande", D("25000"))
    assert e.fee_status == "gratis"
    assert e.fee == D("0.00")


# --- tabela: outras cidades --------------------------------------------------------------------

@pytest.mark.parametrize("city", ["Dourados", "Três Lagoas", "Campo Grandeza", "São Paulo - SP"])
@pytest.mark.parametrize("value", [D("1"), D("499.99"), D("500.00"), D("500.01"), D("9999")])
def test_other_cities_any_value(city, value):
    e = shipping_estimate(city, value)
    assert e.region == "nao_confirmada"
    assert e.fee_status == "nao_disponivel"
    assert e.fee is None
    assert e.deadlines == list(OTHER_CITIES_DEADLINES)
    assert e.notes == [NOTE_SEGURO, NOTE_FRETE_ESPECIAL]
    assert e.limitations == [LIMITATION_P8, LIMITATION_VALOR_POR_CEP]
    assert e.limitations[0] is LIMITATION_P8
    assert e.limitations[1] is LIMITATION_VALOR_POR_CEP


def test_other_cities_deadlines_are_pac_sedex_jadlog():
    e = shipping_estimate("Dourados", D("300"))
    assert len(e.deadlines) == 3
    assert e.deadlines[0].startswith("PAC")
    assert e.deadlines[1].startswith("SEDEX")
    assert e.deadlines[2].startswith("Jadlog")


# --- P13: o agente não classifica produto ---------------------------------------------------------

def test_special_freight_note_only_for_other_cities():
    assert NOTE_FRETE_ESPECIAL in shipping_estimate("Dourados", D("5000")).notes
    for city, value in [
        ("Campo Grande", D("5000")),
        ("Campo Grande", D("100")),
        ("Campo Grande", D("500")),
        (None, D("100")),
        ("", D("100")),
    ]:
        assert NOTE_FRETE_ESPECIAL not in shipping_estimate(city, value).notes


def test_seguro_note_only_for_other_cities():
    assert NOTE_SEGURO not in shipping_estimate("Campo Grande", D("100")).notes
    assert NOTE_SEGURO in shipping_estimate("Dourados", D("100")).notes


def test_shipping_estimate_takes_no_product_argument():
    assert list(inspect.signature(shipping_estimate).parameters) == ["city", "order_value"]


# --- cidade não informada ---------------------------------------------------------------------

@pytest.mark.parametrize("city", [None, "", "   ", "\t\n"])
@pytest.mark.parametrize("value", [D("100"), D("500"), D("1000")])
def test_city_not_informed(city, value):
    e = shipping_estimate(city, value)
    assert e.region == "nao_confirmada"
    assert e.fee_status == "nao_disponivel"
    assert e.fee is None
    assert e.deadlines == []
    assert e.notes == []
    assert e.limitations == [LIMITATION_CIDADE_NAO_INFORMADA]
    assert e.limitations[0] is LIMITATION_CIDADE_NAO_INFORMADA


# --- valores inválidos ----------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value",
    [D("0"), D("0.00"), D("-1"), D("-500.01"), D("NaN"), D("Infinity"), D("-Infinity"), 600.0, 499.99, None],
)
@pytest.mark.parametrize("city", ["Campo Grande", "Dourados", None, ""])
def test_invalid_order_value_raises(city, value):
    with pytest.raises(ValueError):
        shipping_estimate(city, value)


# --- modelo ------------------------------------------------------------------------------------------------

def test_estimate_is_frozen():
    e = shipping_estimate("Campo Grande", D("600"))
    with pytest.raises(Exception):
        e.fee_status = "taxa_fixa"


# --- arquitetura ----------------------------------------------------------------------------------------------

def test_domain_does_not_import_data_or_config_layers():
    source = Path(shipping.__file__).read_text(encoding="utf-8")
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any(m.startswith(("emporio_agent.data", "emporio_agent.config")) for m in imported)
