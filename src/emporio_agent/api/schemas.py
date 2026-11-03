"""Modelos Pydantic de requisição, resposta e erro da API HTTP."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_MESSAGE_LENGTH = 2000
MAX_SESSION_ID_LENGTH = 64

MSG_EMPTY = "A mensagem não pode ficar vazia."
MSG_TOO_LONG = f"A mensagem pode ter no máximo {MAX_MESSAGE_LENGTH} caracteres."


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = Field(description="`ok` quando o agente está pronto; `degraded` caso contrário.")
    agent_ready: bool = Field(description="Indica se o agente foi montado e pode responder.")
    provider: str = Field(description="Provedor de IA configurado.")
    model: str = Field(description="Modelo de IA configurado.")
    detail: str | None = Field(default=None, description="Motivo do modo degradado, em português (sem segredos).")


class SessionCreated(BaseModel):
    session_id: str = Field(description="Identificador da sessão (guardado só em memória).")
    greeting: str = Field(description="Saudação inicial da Mel.")
    created_at: str = Field(description="Data/hora de criação (ISO 8601, fuso da loja).")


class ChatRequest(BaseModel):
    session_id: str | None = Field(
        default=None,
        max_length=MAX_SESSION_ID_LENGTH,
        description="Sessão existente. Nulo ou ausente cria uma sessão nova.",
    )
    message: str = Field(
        description=f"Mensagem do cliente (1 a {MAX_MESSAGE_LENGTH} caracteres, sem contar espaços nas pontas).",
        examples=["Vocês têm violão para iniciante?"],
    )

    @field_validator("message")
    @classmethod
    def _strip_and_bound(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError(MSG_EMPTY)
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(MSG_TOO_LONG)
        return value


class ToolCallInfo(BaseModel):
    """Resumo de uma ferramenta usada. Os argumentos nunca são expostos (podem conter dados pessoais)."""

    name: str = Field(description="Nome da ferramenta.")
    ok: bool = Field(description="Se a ferramenta executou sem erro.")
    duration_ms: int = Field(description="Duração da execução, em milissegundos.")


class ChatResponse(BaseModel):
    session_id: str = Field(description="Sessão usada (ou criada) nesta mensagem.")
    reply: str = Field(description="Resposta da Mel.")
    stop: str = Field(
        description="Motivo de término: end_turn, max_tokens, refusal, max_iterations ou llm_error."
    )
    tool_calls: list[ToolCallInfo] = Field(description="Ferramentas usadas para compor a resposta.")


class ErrorResponse(BaseModel):
    error: str = Field(description="Código do erro (ex.: invalid_request, session_not_found).")
    message: str = Field(description="Mensagem em português para o usuário.")
