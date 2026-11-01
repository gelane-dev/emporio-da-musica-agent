"""Detecção de conflitos de cadastro de produtos (DATA_ANALYSIS.md §3.1).

Duas camadas, nenhuma altera valores:

1. Verificações automáticas: marca citada na descrição × marca do nome;
   número de cordas e de teclas na descrição × ``specs``.
2. Lista revisada manualmente, para casos que a heurística não cobre sem
   gerar falsos positivos. Cada item só é aplicado se a evidência ainda
   estiver presente nos dados (se o cadastro for corrigido, o item deixa de valer).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from emporio_agent.data.models import ProductConflict

# Fabricantes de instrumentos presentes nos dados. Marcas de componentes
# (ex.: LR Baggs, Aquila, Atmosfeel) ficam de fora de propósito: citá-las na
# descrição não indica o fabricante do instrumento.
INSTRUMENT_BRANDS: tuple[str, ...] = (
    "Crafter", "Fender", "Giannini", "Gibson", "Ibanez", "Kala", "Kalani",
    "Korg", "Martin", "Music Man", "Nord", "Ohana", "Pearl", "PRS", "Roland",
    "Rozini", "Shelby", "Tagima", "Takamine", "Tama", "Taylor", "Yamaha",
)

_BRAND_PATTERNS = {
    brand: re.compile(rf"\b{re.escape(brand)}\b", re.IGNORECASE) for brand in INSTRUMENT_BRANDS
}
_STRINGS_PATTERN = re.compile(r"\b(\d+)\s+cordas\b", re.IGNORECASE)
_KEYS_PATTERN = re.compile(r"\b(\d+)\s+teclas\b", re.IGNORECASE)


def brands_in(text: str) -> set[str]:
    """Marcas de instrumento citadas no texto."""
    return {brand for brand, pattern in _BRAND_PATTERNS.items() if pattern.search(text)}


def _brand_conflict(product_id: int, name: str, description: str, specs: dict[str, str]):
    name_brands = brands_in(name)
    description_brands = brands_in(description)
    if not name_brands or not description_brands or name_brands & description_brands:
        return None
    return ProductConflict(
        product_id=product_id,
        kind="marca",
        fields=("name", "description"),
        values={
            "name": ", ".join(sorted(name_brands)),
            "description": ", ".join(sorted(description_brands)),
        },
        detection="automatica",
        note="O nome e a descrição citam fabricantes diferentes.",
    )


def _numeric_conflict(kind: str, pattern: re.Pattern[str], spec_key: str, label: str):
    def check(product_id: int, name: str, description: str, specs: dict[str, str]):
        match = pattern.search(description)
        spec_value = specs.get(spec_key, "").strip()
        if not match or not spec_value.isdigit() or match.group(1) == spec_value:
            return None
        return ProductConflict(
            product_id=product_id,
            kind=kind,
            fields=("description", f"specs.{spec_key}"),
            values={"description": match.group(1), f"specs.{spec_key}": spec_value},
            detection="automatica",
            note=f"A descrição e as especificações informam números de {label} diferentes.",
        )

    return check


_AUTOMATIC_CHECKS: tuple[Callable[..., ProductConflict | None], ...] = (
    _brand_conflict,
    _numeric_conflict("cordas", _STRINGS_PATTERN, "strings", "cordas"),
    _numeric_conflict("teclas", _KEYS_PATTERN, "keys", "teclas"),
)


@dataclass(frozen=True)
class ReviewedConflict:
    """Conflito identificado em revisão manual, válido enquanto a evidência existir."""

    product_id: int
    evidence: Callable[[str, str, dict[str, str]], bool]  # (name, description, specs) -> bool
    fields: tuple[str, ...]
    values: Callable[[str, str, dict[str, str]], dict[str, str]]
    note: str


REVIEWED_CONFLICTS: tuple[ReviewedConflict, ...] = (
    ReviewedConflict(
        product_id=136,
        evidence=lambda name, desc, specs: "ibanez" in name.lower() and "precision" in desc.lower(),
        fields=("name", "description"),
        values=lambda name, desc, specs: {"name": "Ibanez", "description": "Precision"},
        note="O nome indica Ibanez, mas a descrição cita o modelo Precision, de outro fabricante.",
    ),
    ReviewedConflict(
        product_id=143,
        evidence=lambda name, desc, specs: (
            "piano de palco" in desc.lower() and specs.get("type", "").lower() == "synthesizer"
        ),
        fields=("description", "specs.type"),
        values=lambda name, desc, specs: {
            "description": "piano de palco",
            "specs.type": specs.get("type", ""),
        },
        note="A descrição diz piano de palco, mas as especificações indicam sintetizador.",
    ),
)


def detect_product_conflicts(products: pd.DataFrame) -> dict[int, list[ProductConflict]]:
    """Retorna os conflitos por ``product_id`` (só produtos com conflito aparecem).

    Espera o DataFrame normalizado do loader (colunas ``product_id``, ``name``,
    ``description`` e ``specs`` como ``dict``).
    """
    conflicts: dict[int, list[ProductConflict]] = {}
    rows = {
        int(row.product_id): (row.name, row.description, row.specs)
        for row in products.itertuples(index=False)
    }

    for product_id, (name, description, specs) in rows.items():
        for check in _AUTOMATIC_CHECKS:
            conflict = check(product_id, name, description, specs)
            if conflict is not None:
                conflicts.setdefault(product_id, []).append(conflict)

    for reviewed in REVIEWED_CONFLICTS:
        if reviewed.product_id not in rows:
            continue
        name, description, specs = rows[reviewed.product_id]
        if not reviewed.evidence(name, description, specs):
            continue
        conflicts.setdefault(reviewed.product_id, []).append(
            ProductConflict(
                product_id=reviewed.product_id,
                kind="revisao_manual",
                fields=reviewed.fields,
                values=reviewed.values(name, description, specs),
                detection="revisao_manual",
                note=reviewed.note,
            )
        )

    return dict(sorted(conflicts.items()))
