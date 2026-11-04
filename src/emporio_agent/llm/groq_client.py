"""Adaptador do provedor Groq (ARCHITECTURE §5.6.2, TECHNICAL_DECISIONS D17)."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import groq

from emporio_agent.llm.base import (
    LLMError,
    LLMResponse,
    Message,
    StopReason,
    ToolCall,
    ToolSpec,
)

logger = logging.getLogger(__name__)

_STOP_REASONS: dict[str, StopReason] = {
    "stop": "end_turn",
    "tool_calls": "tool_use",
    "length": "max_tokens",
    "content_filter": "refusal",
}
_EFFORT_MAP = {"low": "low", "medium": "medium", "high": "high", "xhigh": "high", "max": "high"}


def _is_gpt_oss(model: str) -> bool:
    return model.startswith("openai/gpt-oss-")


def to_groq_messages(system: str, system_dynamic: str | None, messages: list[Message]) -> list[dict]:
    """Converte o formato neutro para ``messages`` da API de chat da Groq."""
    out: list[dict] = [{"role": "system", "content": system}]
    if system_dynamic:
        out.append({"role": "system", "content": system_dynamic})
    for msg in messages:
        if msg.role == "user":
            out.append({"role": "user", "content": msg.content or ""})
        elif msg.role == "tool":
            out.append(
                {"role": "tool", "tool_call_id": msg.tool_call_id, "content": msg.content or ""}
            )
        else:
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content or None}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, ensure_ascii=False),
                        },
                    }
                    for call in msg.tool_calls
                ]
            out.append(entry)
    return out


def to_groq_tools(tools: list[ToolSpec]) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def _parse_arguments(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def from_groq_response(response: Any) -> LLMResponse:
    """Converte ``groq.types.chat.ChatCompletion`` para ``LLMResponse``."""
    choice = response.choices[0]
    message = choice.message
    calls = [
        ToolCall(
            id=call.id,
            name=call.function.name,
            arguments=_parse_arguments(call.function.arguments),
        )
        for call in (message.tool_calls or [])
    ]
    raw = choice.finish_reason
    usage: dict[str, int] = {}
    if getattr(response, "usage", None) is not None:
        usage = {
            "input_tokens": int(response.usage.prompt_tokens or 0),
            "output_tokens": int(response.usage.completion_tokens or 0),
        }
    return LLMResponse(
        text=message.content or None,
        tool_calls=calls,
        stop_reason=_STOP_REASONS.get(raw, "other") if raw else "other",
        raw_stop_reason=raw,
        usage=usage,
        provider_content=None,
    )


_RETRYABLE_CODES = frozenset({"tool_use_failed", "output_parse_failed"})
_DEGENERATE_MIN_LINES = 5


def is_degenerate(text: str | None) -> bool:
    """``True`` se há ≥ 5 linhas não vazias só de pontuação, reticências, travessões, asteriscos,
    espaços ou caracteres de largura zero (raciocínio vazando para o conteúdo)."""
    if not text:
        return False
    junk = sum(
        1 for line in text.splitlines() if line.strip() and not any(ch.isalnum() for ch in line)
    )
    return junk >= _DEGENERATE_MIN_LINES


def _error_code(exc: groq.BadRequestError) -> str | None:
    """``error.code`` do corpo do 400, só se for uma string curta e segura."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            code = error.get("code")
            if isinstance(code, str) and code and all(ch.isalnum() or ch in "_-." for ch in code[:64]):
                return code[:64]
    return None


def _map_error(exc: groq.APIError) -> LLMError:
    """Exceção do SDK ⇒ ``LLMError`` (mensagens fixas: nunca incluem a chave nem o texto da API)."""
    if isinstance(exc, (groq.AuthenticationError, groq.PermissionDeniedError)):
        return LLMError(
            "auth",
            "A API recusou as credenciais. Verifique GROQ_API_KEY no arquivo .env "
            "(chave válida e com acesso ao modelo configurado).",
        )
    if isinstance(exc, groq.RateLimitError):
        return LLMError(
            "rate_limit", "Limite de requisições da API atingido. Tente novamente em instantes."
        )
    if isinstance(exc, groq.APIConnectionError):  # inclui APITimeoutError
        return LLMError(
            "connection",
            "Não foi possível conectar à API (rede ou tempo esgotado). Tente novamente.",
        )
    if isinstance(exc, groq.BadRequestError):
        # Nunca interpolar `exc.message`: o texto bruto da API pode ecoar a requisição.
        message = (
            "A API rejeitou a requisição (HTTP 400). Verifique a configuração do modelo "
            "(LLM_MODEL, LLM_EFFORT)."
        )
        request_id = None
        response = getattr(exc, "response", None)
        if response is not None:
            request_id = response.headers.get("x-request-id")
        if isinstance(request_id, str) and request_id:
            safe_id = "".join(ch for ch in request_id[:64] if ch.isalnum() or ch in "_-")
            if safe_id:
                message += f" (request id: {safe_id})"
        return LLMError("bad_request", message)
    status = getattr(exc, "status_code", None)
    if isinstance(exc, groq.APIStatusError) and status is not None and status >= 500:
        return LLMError(
            "server", f"A API está indisponível no momento (HTTP {status}). Tente novamente."
        )
    return LLMError("api", f"Erro inesperado da API: {type(exc).__name__}.")


_MAX_RETRY_AFTER_SECONDS = 90.0


def _retry_after_seconds(exc: groq.RateLimitError) -> float | None:
    """Valor do cabeçalho ``retry-after`` (segundos), ou ``None`` se ausente/inválido."""
    response = getattr(exc, "response", None)
    raw = response.headers.get("retry-after") if response is not None else None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


class GroqClient:
    """Implementa ``LLMClient`` sobre o SDK oficial da Groq."""

    def __init__(
        self,
        *,
        model: str,
        effort: str,
        api_key: str | None = None,
        client: groq.Groq | None = None,
        max_retries: int = 5,
        timeout: float = 60.0,
        tool_use_failed_retries: int = 1,
        rate_limit_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._model = model
        self._effort = effort
        self._tool_use_failed_retries = tool_use_failed_retries
        self._rate_limit_retries = rate_limit_retries
        self._sleep = sleep
        self._client = client or groq.Groq(
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
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": to_groq_messages(system, system_dynamic, messages),
            "max_completion_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = to_groq_tools(tools)
            kwargs["tool_choice"] = "auto"
        if _is_gpt_oss(self._model):
            kwargs["reasoning_effort"] = _EFFORT_MAP.get(self._effort, "low")
            kwargs["include_reasoning"] = False

        attempt = 0
        rate_attempt = 0
        degenerate_retried = False
        while True:
            try:
                response = self._client.chat.completions.create(**kwargs)
            except groq.BadRequestError as exc:
                code = _error_code(exc)
                if code in _RETRYABLE_CODES and attempt < self._tool_use_failed_retries:
                    attempt += 1
                    logger.warning(
                        "Groq: erro de geração (%s) (tentativa %d/%d); repetindo a requisição.",
                        code,
                        attempt,
                        self._tool_use_failed_retries,
                    )
                    continue
                if code is not None:
                    logger.warning("Groq: HTTP 400 (error.code=%s).", code)
                raise _map_error(exc) from None
            except groq.RateLimitError as exc:
                # O SDK já esgotou suas retries; espera extra só se o retry-after for curto.
                wait = _retry_after_seconds(exc)
                if (
                    wait is not None
                    and wait <= _MAX_RETRY_AFTER_SECONDS
                    and rate_attempt < self._rate_limit_retries
                ):
                    rate_attempt += 1
                    logger.warning(
                        "Groq: limite de vazão (tentativa %d/%d); aguardando %.1f s.",
                        rate_attempt,
                        self._rate_limit_retries,
                        wait,
                    )
                    self._sleep(wait)
                    continue
                raise _map_error(exc) from None
            except groq.APIError as exc:
                raise _map_error(exc) from None
            result = from_groq_response(response)
            if is_degenerate(result.text):
                if not degenerate_retried:
                    degenerate_retried = True
                    logger.warning("Groq: resposta degenerada; repetindo a requisição uma vez.")
                    continue
                logger.warning("Groq: resposta degenerada também na repetição; usando a 2ª.")
            return result
