"""Sessão de conversa: histórico append-only e transcript (ARCHITECTURE §5.7.2)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime

from emporio_agent.llm.base import Message


class Session:
    def __init__(self, started_at: datetime, session_id: str | None = None) -> None:
        self.id: str = session_id or uuid.uuid4().hex[:8]
        self.started_at: datetime = started_at
        self.messages: list[Message] = []

    def add_user(self, text: str) -> None:
        self.messages.append(Message(role="user", content=text))

    def add(self, message: Message) -> None:
        self.messages.append(message)

    def window(self, max_turns: int) -> list[Message]:
        """Cópia a partir do início do ``max_turns``-ésimo turno mais recente.

        Turno = começa numa mensagem ``user``. Com poucos turnos devolve tudo.
        """
        starts = [i for i, m in enumerate(self.messages) if m.role == "user"]
        if max_turns <= 0 or len(starts) <= max_turns:
            return list(self.messages)
        return list(self.messages[starts[-max_turns] :])

    def to_markdown(self) -> str:
        lines = [
            "# Conversa — Empório da Música",
            "",
            f"Sessão: {self.id} · Início: {self.started_at:%d/%m/%Y %H:%M}",
            "",
        ]
        statuses = {m.tool_call_id: ("erro" if m.is_error else "ok") for m in self.messages if m.role == "tool"}
        for message in self.messages:
            if message.role == "user":
                lines += [f"**Cliente:** {message.content or ''}", ""]
            elif message.role == "assistant":
                if message.content:
                    lines += [f"**Mel:** {message.content}", ""]
                for call in message.tool_calls:
                    args = json.dumps(call.arguments, ensure_ascii=False, separators=(",", ":"))
                    status = statuses.get(call.id)
                    suffix = f" ({status})" if status else ""
                    lines.append(f"> Ferramenta: `{call.name}` {args}{suffix}")
                if message.tool_calls:
                    lines.append("")
        return "\n".join(lines).rstrip() + "\n"
