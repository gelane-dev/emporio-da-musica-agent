"""Ferramenta encaminhar_atendente (§5.5.2).

Registra o encaminhamento em ``runtime_dir/handoffs.jsonl`` (uma linha JSON por chamada) depois de
mascarar e-mails e números longos do resumo.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from emporio_agent.domain.limitations import Limitation
from emporio_agent.tools.base import Tool, ToolArgs, ToolResult
from emporio_agent.tools.limitations import MANUAL

HANDOFF_FILE = "handoffs.jsonl"
COMPLAINT_DEADLINE = "24 horas úteis"

_EMAIL_RE = re.compile(r"[^\s@<>()\[\],;:]+@[^\s@<>()\[\],;:]+\.[^\s@<>()\[\],;:]+")
# 8 ou mais dígitos, ignorando espaços, parênteses, pontos e hífens entre eles.
_LONG_NUMBER_RE = re.compile(r"\(?\d(?:[\s().\-]*\d){7,}")

LIMITATION_PRAZO_RETORNO = Limitation(
    code="MANUAL_OMISSO",
    message=(
        "O manual só define prazo de retorno para reclamações. Neste caso, não prometa prazo: "
        "diga apenas que a equipe entrará em contato."
    ),
    source=f"{MANUAL}, seção 7.3",
)


def mask_sensitive(text: str) -> str:
    """Remove e-mails e sequências de 8+ dígitos (telefones, CPF etc.) do texto."""
    text = _EMAIL_RE.sub("[e-mail removido]", text)
    return _LONG_NUMBER_RE.sub("[número removido]", text)


class EncaminharAtendenteArgs(ToolArgs):
    motivo: Literal["reclamacao", "caso_complexo", "pedido_cliente"] = Field(
        description=(
            "reclamacao: cliente insatisfeito ou reclamando; caso_complexo: situação que as "
            "ferramentas e o manual não resolvem; pedido_cliente: cliente pediu um atendente humano."
        )
    )
    resumo: str = Field(
        min_length=1,
        max_length=1000,
        description=(
            "Resumo objetivo do caso para o atendente. Não inclua e-mail, telefone ou outros dados "
            "pessoais do cliente."
        ),
    )
    pedido_id: int | None = Field(default=None, ge=1, description="Número do pedido, se houver.")

    @field_validator("resumo", mode="before")
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value


class EncaminharAtendente(Tool):
    name = "encaminhar_atendente"
    description = (
        "Registra a reclamação ou o caso e o encaminha a um atendente humano, devolvendo um "
        "protocolo para o cliente. Use quando o cliente fizer uma reclamação, pedir para falar com "
        "uma pessoa ou quando o caso não puder ser resolvido com as demais ferramentas e o manual. "
        "O prazo de retorno de 24 horas úteis só vale para reclamações."
    )
    args_model = EncaminharAtendenteArgs

    def __init__(self, runtime_dir: Path, clock: Callable[[], datetime]):
        self._path = Path(runtime_dir) / HANDOFF_FILE
        self._clock = clock

    def run(self, args: EncaminharAtendenteArgs) -> ToolResult:  # type: ignore[override]
        now = self._clock()
        protocol = f"EM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        record = {
            "protocolo": protocol,
            "criado_em": now.isoformat(),
            "motivo": args.motivo,
            "resumo": mask_sensitive(args.resumo),
            "pedido_id": args.pedido_id,
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        is_complaint = args.motivo == "reclamacao"
        data = {
            "protocolo": protocol,
            "motivo": args.motivo,
            "prazo_retorno": COMPLAINT_DEADLINE if is_complaint else None,
        }
        return ToolResult.success(data, [] if is_complaint else [LIMITATION_PRAZO_RETORNO])
