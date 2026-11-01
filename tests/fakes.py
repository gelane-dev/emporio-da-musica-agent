"""Dublês de teste compartilhados (T08; usados pelas T10/T11)."""

from __future__ import annotations

import copy

from emporio_agent.llm.base import LLMResponse, Message, ToolCall, ToolSpec


class FakeLLM:
    """``LLMClient`` roteirizável: devolve (ou lança) o próximo item de ``responses``."""

    def __init__(self, responses: list[LLMResponse | Exception]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(
        self,
        *,
        system: str,
        system_dynamic: str | None,
        messages: list[Message],
        tools: list[ToolSpec],
        max_tokens: int,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "system_dynamic": system_dynamic,
                "messages": copy.deepcopy(messages),
                "tools": tools,
                "max_tokens": max_tokens,
            }
        )
        if not self._responses:
            raise AssertionError("FakeLLM sem respostas roteirizadas restantes")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def fake_text(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        tool_calls=[],
        stop_reason="end_turn",
        raw_stop_reason="end_turn",
        usage={"input_tokens": 0, "output_tokens": 0},
        provider_content=None,
    )


def fake_tool_calls(*calls: tuple[str, dict], ids: list[str] | None = None) -> LLMResponse:
    ids = ids or [f"toolu_fake_{i}" for i in range(1, len(calls) + 1)]
    assert len(ids) == len(calls), "ids e calls precisam ter o mesmo tamanho"
    return LLMResponse(
        text=None,
        tool_calls=[ToolCall(id=i, name=n, arguments=a) for i, (n, a) in zip(ids, calls)],
        stop_reason="tool_use",
        raw_stop_reason="tool_use",
        usage={"input_tokens": 0, "output_tokens": 0},
        provider_content=None,
    )
