"""Infraestrutura das ferramentas expostas ao LLM (ARCHITECTURE §5.5 e §5.5.1).

``ToolRegistry.execute`` nunca lança: qualquer falha vira ``ToolResult(ok=False)``.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from emporio_agent.domain.limitations import Limitation
from emporio_agent.llm.base import ToolSpec

logger = logging.getLogger(__name__)

ToolErrorCode = Literal["NOT_FOUND", "AMBIGUOUS", "VERIFICATION_FAILED", "VERIFICATION_LOCKED", "INVALID_ARGUMENT", "INTERNAL_ERROR"]


# Conversa em andamento, para ferramentas que precisam de estado POR conversa (ex.: limite de
# tentativas de verificação). O registry é compartilhável entre sessões; o id viaja por contexto.
_CONVERSATION_ID: ContextVar[str | None] = ContextVar("conversation_id", default=None)


def current_conversation_id() -> str | None:
    """Id da conversa; ``None`` fora do agente (chamada direta, sem sessão: nada a limitar)."""
    return _CONVERSATION_ID.get()


class ToolError(BaseModel, frozen=True):
    code: ToolErrorCode
    message: str
    """Texto em português que diz ao LLM o que fazer."""
    details: dict | None = None


class ToolResult(BaseModel, frozen=True):
    ok: bool
    data: dict | list | None = None
    error: ToolError | None = None
    limitations: list[Limitation] = []

    @classmethod
    def success(cls, data: dict | list, limitations: list[Limitation] | None = None) -> ToolResult:
        return cls(ok=True, data=data, limitations=list(limitations or []))

    @classmethod
    def failure(
        cls,
        code: ToolErrorCode,
        message: str,
        details: dict | None = None,
        limitations: list[Limitation] | None = None,
    ) -> ToolResult:
        return cls(
            ok=False,
            error=ToolError(code=code, message=message, details=details),
            limitations=list(limitations or []),
        )

    def to_llm(self) -> str:
        """JSON compacto em português, sem limitações duplicadas (mesmo código e mensagem)."""
        payload: dict[str, Any] = {"ok": self.ok}
        if self.data is not None:
            payload["dados"] = self.data
        if self.error is not None:
            erro: dict[str, Any] = {"codigo": self.error.code, "mensagem": self.error.message}
            if self.error.details:
                erro["detalhes"] = self.error.details
            payload["erro"] = erro
        seen: set[tuple[str, str]] = set()
        limitacoes = []
        for limitation in self.limitations:
            key = (limitation.code, limitation.message)
            if key in seen:
                continue
            seen.add(key)
            limitacoes.append(
                {"codigo": limitation.code, "mensagem": limitation.message, "fonte": limitation.source}
            )
        if limitacoes:
            payload["limitacoes"] = limitacoes
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)


class ToolArgs(BaseModel):
    """Base dos modelos de argumentos: argumentos desconhecidos são rejeitados."""

    model_config = ConfigDict(extra="forbid")


class Tool(ABC):
    name: str
    description: str
    args_model: type[BaseModel]

    @abstractmethod
    def run(self, args: BaseModel) -> ToolResult: ...


def _describe_validation_error(exc: ValidationError) -> list[dict[str, str]]:
    """Resume os erros sem ecoar os valores recebidos (podem ser dados do cliente)."""
    problems = []
    for err in exc.errors(include_input=False, include_url=False, include_context=False):
        field = ".".join(str(part) for part in err["loc"]) or "(geral)"
        kind = err["type"]
        if kind == "extra_forbidden":
            problem = "argumento inexistente nesta ferramenta"
        elif kind == "missing":
            problem = "argumento obrigatório ausente"
        else:
            problem = str(err["msg"]).removeprefix("Value error, ")
        problems.append({"campo": field, "problema": problem})
    return problems


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        names = [tool.name for tool in tools]
        duplicated = sorted({n for n in names if names.count(n) > 1})
        if duplicated:
            raise ValueError(f"nomes de ferramenta duplicados: {', '.join(duplicated)}")
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name=tool.name,
                description=tool.description,
                input_schema=tool.args_model.model_json_schema(),
            )
            for tool in self._tools.values()
        ]

    def execute(self, name: str, raw_args: dict, conversation_id: str | None = None) -> ToolResult:
        token = _CONVERSATION_ID.set(conversation_id)
        try:
            return self._execute(name, raw_args)
        finally:
            _CONVERSATION_ID.reset(token)

    def _execute(self, name: str, raw_args: dict) -> ToolResult:
        try:
            tool = self._tools.get(name)
            if tool is None:
                return ToolResult.failure(
                    "INVALID_ARGUMENT",
                    # Não ecoa o nome recebido (pode ser conteúdo arbitrário vindo do modelo/cliente).
                    f"Ferramenta desconhecida. Ferramentas disponíveis: {', '.join(self._tools)}.",
                )
            try:
                args = tool.args_model.model_validate(raw_args)
            except ValidationError as exc:
                problems = _describe_validation_error(exc)
                resumo = "; ".join(f"{p['campo']}: {p['problema']}" for p in problems)
                return ToolResult.failure(
                    "INVALID_ARGUMENT",
                    f"Argumentos inválidos para '{name}' ({resumo}). Corrija e chame a ferramenta de novo.",
                    details={"problemas": problems},
                )
            return tool.run(args)
        except Exception:
            logger.exception("Falha inesperada ao executar a ferramenta %r", name)
            return ToolResult.failure(
                "INTERNAL_ERROR",
                "Ocorreu um erro interno ao consultar essa informação. Não invente dados: avise o "
                "cliente do problema técnico e, se for o caso, ofereça o atendimento da equipe.",
            )
