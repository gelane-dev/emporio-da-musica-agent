"""Ferramentas expostas ao LLM (ARCHITECTURE §5.5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.policies.store import PolicyStore
from emporio_agent.tools.base import Tool, ToolError, ToolRegistry, ToolResult
from emporio_agent.tools.catalog_tools import BuscarProdutos, DetalharProduto, ListarCategorias
from emporio_agent.tools.order_tools import ConsultarPedido
from emporio_agent.tools.policy_tools import ConsultarPolitica, EstimarFrete, InformacoesLoja

__all__ = ["Tool", "ToolError", "ToolRegistry", "ToolResult", "build_tool_registry"]


def build_tool_registry(
    catalog: CatalogRepository,
    orders: OrderRepository,
    policies: PolicyStore,
    clock: Callable[[], datetime],
) -> ToolRegistry:
    return ToolRegistry(
        [
            BuscarProdutos(catalog),
            DetalharProduto(catalog),
            ListarCategorias(catalog),
            ConsultarPedido(orders),
            ConsultarPolitica(policies),
            InformacoesLoja(policies, clock),
            EstimarFrete(),
        ]
    )
