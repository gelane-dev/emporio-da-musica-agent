"""Formato neutro de mensagens e interface ``LLMClient`` (ARCHITECTURE §5.6.1).

Nada aqui depende de um provedor específico; cada provedor tem seu adaptador.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel


class ToolSpec(BaseModel, frozen=True):
    name: str
    description: str
    input_schema: dict


class ToolCall(BaseModel, frozen=True):
    id: str
    name: str
    arguments: dict


class Message(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] = []  # role="assistant"
    tool_call_id: str | None = None  # role="tool"
    is_error: bool = False  # role="tool": resultado de erro
    # role="assistant": blocos BRUTOS do provedor (raciocínio, fallback, tool_use…),
    # reenviados sem alteração no próximo request. O agente nunca edita este campo.
    provider_content: list[dict] | None = None


StopReason = Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]


class LLMResponse(BaseModel):
    text: str | None
    tool_calls: list[ToolCall]
    stop_reason: StopReason
    raw_stop_reason: str | None
    usage: dict[str, int]
    provider_content: list[dict] | None

    def to_message(self) -> Message:
        """Mensagem de assistente com texto, chamadas de ferramenta e blocos brutos."""
        return Message(
            role="assistant",
            content=self.text,
            tool_calls=list(self.tool_calls),
            provider_content=self.provider_content,
        )


LLMErrorKind = Literal["config", "auth", "rate_limit", "connection", "bad_request", "server", "api"]


class LLMError(Exception):
    """Erro do adaptador LLM; ``message`` é em português e acionável."""

    def __init__(self, kind: LLMErrorKind, message: str) -> None:
        super().__init__(message)
        self.kind: LLMErrorKind = kind
        self.message = message

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


class LLMClient(Protocol):
    def complete(
        self,
        *,
        system: str,
        system_dynamic: str | None,
        messages: list[Message],
        tools: list[ToolSpec],
        max_tokens: int,
    ) -> LLMResponse:
        """``system``: parte estável (cacheável); ``system_dynamic``: parte volátil."""
        ...
