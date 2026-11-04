"""Adaptador do provedor Anthropic (ARCHITECTURE §5.6.1, TECHNICAL_DECISIONS D16)."""

from __future__ import annotations

from typing import Any

import anthropic

from emporio_agent.llm.base import (
    LLMError,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolSpec,
)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
_STOP_REASONS: dict[str, StopReason] = {
    "end_turn": "end_turn",
    "tool_use": "tool_use",
    "max_tokens": "max_tokens",
    "refusal": "refusal",
}


def to_anthropic_messages(messages: list[Message]) -> list[dict]:
    """Converte o formato neutro para ``messages`` da API Anthropic."""
    out: list[dict] = []
    pending_results: list[dict] = []

    def flush() -> None:
        if pending_results:
            out.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for msg in messages:
        if msg.role == "tool":
            pending_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content or "",
                    "is_error": msg.is_error,
                }
            )
            continue
        flush()
        if msg.role == "user":
            out.append({"role": "user", "content": msg.content or ""})
        elif msg.provider_content is not None:
            out.append({"role": "assistant", "content": msg.provider_content})
        else:
            blocks: list[dict] = []
            if msg.content:
                blocks.append({"type": "text", "text": msg.content})
            for call in msg.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
                )
            out.append({"role": "assistant", "content": blocks})
    flush()
    return out


def from_anthropic_response(response: Any) -> LLMResponse:
    """Converte ``anthropic.types.Message`` (ou beta) para ``LLMResponse``."""
    texts: list[str] = []
    calls: list[ToolCall] = []
    for block in response.content:
        if block.type == "text":
            texts.append(block.text)
        elif block.type == "tool_use":
            calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
    raw = response.stop_reason
    usage: dict[str, int] = {}
    if getattr(response, "usage", None) is not None:
        usage = {
            k: v
            for k, v in response.usage.model_dump(mode="json").items()
            if isinstance(v, int) and not isinstance(v, bool)
        }
    return LLMResponse(
        text="\n".join(texts) if texts else None,
        tool_calls=calls,
        stop_reason=_STOP_REASONS.get(raw, "other") if raw else "other",
        raw_stop_reason=raw,
        usage=usage,
        provider_content=[b.model_dump(mode="json", exclude_none=True) for b in response.content],
    )


def _map_error(exc: anthropic.APIError) -> LLMError:
    """Exceção do SDK ⇒ ``LLMError`` (mensagens fixas: nunca incluem a chave)."""
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return LLMError(
            "auth",
            "A API recusou as credenciais. Verifique ANTHROPIC_API_KEY no arquivo .env "
            "(chave válida e com acesso ao modelo configurado).",
        )
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError(
            "rate_limit", "Limite de requisições da API atingido. Tente novamente em instantes."
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError(
            "connection",
            "Não foi possível conectar à API (rede ou tempo esgotado). Tente novamente.",
        )
    if isinstance(exc, anthropic.BadRequestError):
        # Nunca interpolar `exc.message`: o texto bruto da API pode ecoar a requisição (e a chave).
        message = (
            "A API rejeitou a requisição (HTTP 400). Verifique a configuração do modelo "
            "(LLM_MODEL, LLM_EFFORT, LLM_REFUSAL_FALLBACK)."
        )
        request_id = getattr(exc, "request_id", None)
        if isinstance(request_id, str) and request_id:
            safe_id = "".join(ch for ch in request_id[:64] if ch.isalnum() or ch in "_-")
            if safe_id:
                message += f" (request id: {safe_id})"
        return LLMError("bad_request", message)
    status = getattr(exc, "status_code", None)
    if isinstance(exc, anthropic.APIStatusError) and status is not None and status >= 500:
        return LLMError(
            "server", f"A API está indisponível no momento (HTTP {status}). Tente novamente."
        )
    return LLMError("api", f"Erro inesperado da API: {type(exc).__name__}.")


class AnthropicClient:
    """Implementa ``LLMClient`` sobre o SDK oficial."""

    def __init__(
        self,
        *,
        model: str,
        effort: str,
        refusal_fallback: bool,
        api_key: str | None = None,
        client: anthropic.Anthropic | None = None,
        max_retries: int = 2,
        timeout: float = 60.0,
    ) -> None:
        self._model = model
        self._effort = effort
        self._refusal_fallback = refusal_fallback
        self._client = client or anthropic.Anthropic(
            api_key=api_key, max_retries=max_retries, timeout=timeout  # sem timeout, um provedor travado prende a thread
        )

    def complete(
        self,
        *,
        system: str,
        system_dynamic: str | None,
        messages: list[Message],
        tools: list[ToolSpec],
        max_tokens: int,
    ) -> LLMResponse:
        system_blocks: list[dict] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]
        if system_dynamic:
            system_blocks.append({"type": "text", "text": system_dynamic})
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_blocks,
            "messages": to_anthropic_messages(messages),
            "output_config": {"effort": self._effort},
        }
        if tools:
            kwargs["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                for t in tools
            ]
        try:
            if self._refusal_fallback:
                # `fallbacks` é argumento nativo no SDK 2.3.0 (não precisa de extra_body).
                response = self._client.beta.messages.create(
                    **kwargs, betas=[FALLBACK_BETA], fallbacks="default"
                )
            else:
                response = self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            raise _map_error(exc) from None
        return from_anthropic_response(response)
