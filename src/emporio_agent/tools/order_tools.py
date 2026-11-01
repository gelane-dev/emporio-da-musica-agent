"""Ferramenta consultar_pedido (§5.5.1).

Identificação do cliente: número do pedido **e** e-mail ou telefone conferidos contra o cliente
daquele pedido. Pedido inexistente e dado que não confere recebem a mesma resposta.
"""

from __future__ import annotations

import logging
import re
from datetime import date

from pydantic import Field, model_validator

from emporio_agent.data.repository import OrderRepository
from emporio_agent.domain.pricing import format_brl
from emporio_agent.tools.base import Tool, ToolArgs, ToolResult
from emporio_agent.tools.limitations import LIMITATION_P6, LIMITATION_P7

logger = logging.getLogger(__name__)

STATUS_DESCRIPTION = {
    "pending": "pendente",
    "confirmed": "confirmado",
    "shipped": "enviado",
    "delivered": "entregue",
    "cancelled": "cancelado",
}

_CREDIT_RE = re.compile(r"^credit_(\d+)x$")

VERIFICATION_FAILED_MESSAGE = (
    "Os dados não conferem. Peça ao cliente o número do pedido e o e-mail ou telefone usado na "
    "compra; não revele dados do pedido nem diga se o pedido existe."
)


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def payment_description(method: str) -> str:
    fixed = {"pix": "PIX", "debit": "Cartão de débito", "boleto": "Boleto bancário"}
    if method in fixed:
        return fixed[method]
    match = _CREDIT_RE.match(method)
    if match:
        return f"Cartão de crédito em {match.group(1)}x"
    return method


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


class ConsultarPedidoArgs(ToolArgs):
    pedido_id: int = Field(ge=1, description="Número do pedido informado pelo cliente.")
    email: str | None = Field(default=None, description="E-mail usado na compra.")
    telefone: str | None = Field(default=None, description="Telefone usado na compra (com DDD).")

    @model_validator(mode="after")
    def _needs_proof(self) -> ConsultarPedidoArgs:
        if not (self.email and self.email.strip()) and not (self.telefone and _digits(self.telefone)):
            raise ValueError("informe o e-mail ou o telefone usado na compra")
        return self


class ConsultarPedido(Tool):
    name = "consultar_pedido"
    description = (
        "Consulta o status de um pedido (situação, itens, valor registrado, rastreio e previsão de "
        "entrega). Exige o número do pedido E o e-mail ou o telefone usado na compra, para "
        "confirmar a identidade; não aceita nome. Use para perguntas sobre pedidos e entregas. "
        "Não decide se uma troca ou devolução é possível: para as regras, use consultar_politica."
    )
    args_model = ConsultarPedidoArgs

    def __init__(self, orders: OrderRepository):
        self._orders = orders

    def _verify(self, args: ConsultarPedidoArgs):
        order = self._orders.get(args.pedido_id)
        if order is None:
            return None
        try:
            customer = self._orders.customer_of(order)
        except KeyError:
            logger.warning("Pedido %s sem cadastro de cliente consistente", order.id)
            return None
        if args.email and args.email.strip():
            if _normalize_email(args.email) != _normalize_email(customer.email):
                return None
        if args.telefone and _digits(args.telefone):
            if _digits(args.telefone) != customer.phone_digits:
                return None
        return order, customer

    def run(self, args: ConsultarPedidoArgs) -> ToolResult:  # type: ignore[override]
        verified = self._verify(args)
        if verified is None:
            return ToolResult.failure("VERIFICATION_FAILED", VERIFICATION_FAILED_MESSAGE)
        order, customer = verified

        data: dict = {
            "pedido_id": order.id,
            "primeiro_nome_cliente": customer.name.split()[0] if customer.name.split() else "",
            "data_pedido": format_date(order.order_date),
            "status": order.status,
            "status_descricao": STATUS_DESCRIPTION[order.status],
            "valor_total_registrado": format_brl(order.total),
            "forma_pagamento": payment_description(order.payment_method),
            "itens": [{"nome": i.product_name, "quantidade": i.quantity} for i in order.items],
        }
        if order.tracking_code:
            data["codigo_rastreio"] = order.tracking_code
        if order.estimated_delivery:
            data["previsao_entrega_estimada"] = format_date(order.estimated_delivery)
        if order.notes:
            data["observacoes"] = order.notes
        limitations = [LIMITATION_P6, LIMITATION_P7] if order.status in ("shipped", "delivered") else []
        return ToolResult.success(data, limitations)
