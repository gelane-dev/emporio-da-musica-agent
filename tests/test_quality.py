"""Testes da T02: detecção de conflitos de cadastro (DATA_ANALYSIS §3.1)."""

from __future__ import annotations

import logging

import pandas as pd
import pytest

from emporio_agent.data.loader import load_all
from emporio_agent.data.quality import brands_in, detect_product_conflicts

EXPECTED_KINDS = {
    135: ["marca"],
    136: ["revisao_manual"],
    137: ["marca", "cordas"],
    139: ["marca"],
    140: ["marca"],
    142: ["marca", "teclas"],
    143: ["revisao_manual"],
    144: ["marca"],
}


def test_conflicting_products_are_exactly_the_expected_ones(store_data):
    kinds = {pid: [c.kind for c in conflicts] for pid, conflicts in store_data.product_conflicts.items()}
    assert kinds == EXPECTED_KINDS


def test_conflict_values_expose_both_sides(store_data):
    marca, teclas = store_data.product_conflicts[142]
    assert marca.values == {"name": "Korg", "description": "Roland"}
    assert marca.fields == ("name", "description")
    assert marca.detection == "automatica"
    assert teclas.values == {"description": "88", "specs.keys": "61"}

    cordas = store_data.product_conflicts[137][1]
    assert cordas.values == {"description": "5", "specs.strings": "4"}


def test_manually_reviewed_conflicts(store_data):
    (ibanez,) = store_data.product_conflicts[136]
    assert ibanez.detection == "revisao_manual"
    assert ibanez.values == {"name": "Ibanez", "description": "Precision"}

    (nord,) = store_data.product_conflicts[143]
    assert nord.values == {"description": "piano de palco", "specs.type": "Synthesizer"}


@pytest.mark.parametrize("product_id", [138, 141, 102, 108, 116, 109, 110, 111, 112, 113, 95, 131])
def test_no_false_positives(store_data, product_id):
    # 138/141: modelo específico da mesma marca; 102/108/116: marcas de componentes;
    # 109–113: violões de 7 cordas; 95/131: produtos coerentes.
    assert product_id not in store_data.product_conflicts


def test_component_brands_are_not_instrument_brands():
    assert brands_in("captação LR Baggs e cordas Aquila") == set()
    assert brands_in("Contrabaixo Music Man StingRay") == {"Music Man"}
    assert brands_in("escala em Rosewood") == set()  # "Kala" não casa dentro de "escala"


def test_reviewed_conflict_disappears_when_evidence_is_gone():
    products = pd.DataFrame(
        [
            {"product_id": 136, "name": "Ibanez Bass 2X", "description": "Baixo Ibanez SR.", "specs": {}},
            {"product_id": 143, "name": "Nord Synth 2", "description": "Sintetizador.", "specs": {"type": "Synthesizer"}},
        ]
    )
    assert detect_product_conflicts(products) == {}


def test_one_warning_per_conflict(data_dir, caplog):
    with caplog.at_level(logging.WARNING, logger="emporio_agent.data.loader"):
        load_all(data_dir)
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == sum(len(v) for v in EXPECTED_KINDS.values()) == 10
    assert all("@" not in r.getMessage() for r in warnings)
