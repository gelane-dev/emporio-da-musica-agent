"""Loop de tool use: LLM ⇄ ferramentas (ARCHITECTURE §5.7.2)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from emporio_agent import config
from emporio_agent.agent.output_guard import sanitize_reply
from emporio_agent.agent.prompts import build_dynamic_context, build_system_prompt
from emporio_agent.agent.session import Session
from emporio_agent.config import Settings
from emporio_agent.domain.store_hours import store_status
from emporio_agent.llm.base import LLMClient, LLMError, Message
from emporio_agent.tools.base import ToolRegistry

logger = logging.getLogger(__name__)

FALLBACK_MAX_ITERATIONS = (
    "Desculpe, não consegui concluir essa consulta agora. Pode reformular o pedido? "
    "Se preferir, nossa equipe pode ajudar diretamente."
)
FALLBACK_REFUSAL = (
    "Desculpe, não posso ajudar com esse pedido. Posso ajudar com instrumentos, acessórios, "
    "pedidos ou políticas da loja, ou você pode falar com nossa equipe."
)
FALLBACK_EMPTY = (
    "Desculpe, não consegui elaborar uma resposta agora. Pode repetir ou reformular sua pergunta? "
    "Se preferir, nossa equipe pode ajudar."
)
FALLBACK_LLM_ERROR = (
    "Desculpe, estou com um problema técnico no momento e não consegui responder. "
    "Tente novamente em instantes ou fale com nossa equipe."
)

AgentStop = Literal["end_turn", "max_tokens", "refusal", "max_iterations", "llm_error"]

# Ferramentas cujos argumentos contêm dados pessoais: nunca vão para o log.
_SENSITIVE_TOOLS = frozenset({"consultar_pedido", "encaminhar_atendente"})


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict
    ok: bool
    duration_ms: int


class AgentReply(BaseModel):
    text: str
    tool_calls: list[ToolCallRecord]
    stop: AgentStop


class Agent:
    def __init__(
        self,
        llm: LLMClient,
        tools: ToolRegistry,
        settings: Settings,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._llm = llm
        self._tools = tools
        self._settings = settings
        self._clock = clock or (lambda: config.now(settings))
        self._system = build_system_prompt(tools.names())

    def respond(self, session: Session, user_text: str) -> AgentReply:
        settings = self._settings
        session.add_user(user_text)
        now = self._clock()
        system_dynamic = build_dynamic_context(now, store_status(now, settings.timezone))
        records: list[ToolCallRecord] = []
        rounds = 0

        while True:
            try:
                response = self._llm.complete(
                    system=self._system,
                    system_dynamic=system_dynamic,
                    messages=session.window(settings.max_history_turns),
                    tools=self._tools.specs(),
                    max_tokens=settings.llm_max_tokens,
                )
            except LLMError as exc:
                logger.error("Falha na chamada ao LLM: %s", exc)
                return self._fallback(session, FALLBACK_LLM_ERROR, records, "llm_error")

            logger.info("LLM usage=%s stop_reason=%s", response.usage, response.stop_reason)
            message = response.to_message()
            if not response.tool_calls:
                message = message.model_copy(update={"content": sanitize_reply(message.content or "")})
            session.add(message)

            if not response.tool_calls:
                text = message.content.strip()
                if response.stop_reason == "refusal":
                    if text:
                        return AgentReply(text=message.content, tool_calls=records, stop="refusal")
                    return self._fallback(session, FALLBACK_REFUSAL, records, "refusal", replace_last=True)
                if not text:
                    return self._fallback(session, FALLBACK_EMPTY, records, "end_turn", replace_last=True)
                stop: AgentStop = "max_tokens" if response.stop_reason == "max_tokens" else "end_turn"
                return AgentReply(text=message.content, tool_calls=records, stop=stop)

            if rounds >= settings.max_tool_iterations:
                logger.warning("max_tool_iterations (%d) atingido sem resposta final", settings.max_tool_iterations)
                # Tool calls pendentes precisam de resultado para manter o histórico válido.
                self._answer_pending(session, response.tool_calls)
                return self._fallback(session, FALLBACK_MAX_ITERATIONS, records, "max_iterations")
            rounds += 1

            for call in response.tool_calls:
                started = time.perf_counter()
                result = self._tools.execute(call.name, call.arguments)
                duration_ms = int((time.perf_counter() - started) * 1000)
                records.append(
                    ToolCallRecord(name=call.name, arguments=call.arguments, ok=result.ok, duration_ms=duration_ms)
                )
                if call.name in _SENSITIVE_TOOLS:
                    logger.info("tool=%s ok=%s duration_ms=%d", call.name, result.ok, duration_ms)
                else:
                    logger.info(
                        "tool=%s args=%s ok=%s duration_ms=%d", call.name, call.arguments, result.ok, duration_ms
                    )
                session.add(
                    Message(role="tool", tool_call_id=call.id, content=result.to_llm(), is_error=not result.ok)
                )

    @staticmethod
    def _answer_pending(session: Session, calls: list) -> None:
        for call in calls:
            session.add(
                Message(
                    role="tool",
                    tool_call_id=call.id,
                    content='{"ok":false,"erro":{"codigo":"INTERNAL_ERROR","mensagem":"Chamada não executada."}}',
                    is_error=True,
                )
            )

    @staticmethod
    def _fallback(
        session: Session,
        text: str,
        records: list[ToolCallRecord],
        stop: AgentStop,
        replace_last: bool = False,
    ) -> AgentReply:
        # Histórico append-only e alternado. Exceção: uma resposta vazia sem blocos do provedor
        # (inválida para a API) é substituída pelo texto de fallback em vez de ficar vazia.
        last = session.messages[-1] if session.messages else None
        if replace_last and last is not None and last.role == "assistant" and not last.content and not last.tool_calls:
            if last.provider_content:
                session.add(Message(role="assistant", content=text))
            else:
                session.messages[-1] = Message(role="assistant", content=text)
        else:
            session.add(Message(role="assistant", content=text))
        return AgentReply(text=text, tool_calls=records, stop=stop)
