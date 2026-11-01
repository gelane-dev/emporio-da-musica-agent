"""Limitações explícitas devolvidas quando o manual ou os dados não permitem uma resposta confirmada.

Ver TECHNICAL_DECISIONS.md D15 e DATA_ANALYSIS.md §4.2.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

LimitationCode = Literal[
    "MANUAL_CONTRADITORIO",  # o manual diz coisas diferentes sobre o mesmo ponto
    "MANUAL_OMISSO",  # o manual não cobre o caso
    "DADO_NAO_REGISTRADO",  # a informação não existe nos dados da loja
    "DADO_CONFLITANTE",  # campos do mesmo registro se contradizem
]


class Limitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: LimitationCode
    message: str
    """Texto em português, pronto para o agente repassar ao cliente."""
    source: str
    """Origem da limitação, ex.: ``"Manual v2.1, seções 3 e 3.1"``."""
