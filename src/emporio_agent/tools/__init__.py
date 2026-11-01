"""Ferramentas expostas ao LLM (ARCHITECTURE §5.5)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from emporio_agent.data.repository import CatalogRepository, OrderRepository
from emporio_agent.policies.store import PolicyStore
from emporio_agent.tools.base import Tool, ToolError, ToolRegistry, ToolResult
from emporio_agent.tools.catalog_tools import BuscarProdutos, DetalharProduto, ListarCategorias
from emporio_agent.tools.handoff_tools import EncaminharAtendente
from emporio_agent.tools.order_tools import ConsultarPedido
from emporio_agent.tools.policy_tools import ConsultarPolitica, EstimarFrete, InformacoesLoja

__all__ = ["Tool", "ToolError", "ToolRegistry", "ToolResult", "build_tool_registry"]


def build_tool_registry(
    catalog: CatalogRepository,
    orders: OrderRepository,
    policies: PolicyStore,
    clock: Callable[[], datetime],
    runtime_dir: Path | None = None,
) -> ToolRegistry:
    tools: list[Tool] = [
        BuscarProdutos(catalog),
        DetalharProduto(catalog),
        ListarCategorias(catalog),
        ConsultarPedido(orders),
        ConsultarPolitica(policies),
        InformacoesLoja(policies, clock),
        EstimarFrete(),
    ]
    if runtime_dir is not None:
        tools.append(EncaminharAtendente(runtime_dir, clock))
    return ToolRegistry(tools)
