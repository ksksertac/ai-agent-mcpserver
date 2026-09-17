"""Ajan döngüsü — beyin (Ollama) ile eller (MCP) arasındaki turları yönetir.

    messages + tools → Ollama
        ├─ düz cevap → bitti
        └─ tool_calls → her birini MCP'de çalıştır → role:tool mesajı ekle → tekrar Ollama
    (MAX_TOOL_ROUNDS ile sınırlı)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from local_llm.agent.mcp_client import MCPToolRegistry
from local_llm.agent.prompts import SYSTEM_PROMPT
from local_llm.config import settings
from local_llm.ollama_client import OllamaClient, OllamaError

log = logging.getLogger("local_llm.agent.loop")


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass
class AgentResult:
    content: str
    traces: list[ToolTrace] = field(default_factory=list)
    rounds: int = 0


class AgentLoop:
    def __init__(self, ollama: OllamaClient, registry: MCPToolRegistry, max_rounds: int | None = None):
        self.ollama = ollama
        self.registry = registry
        self.max_rounds = max_rounds or settings.max_tool_rounds

    async def run(self, messages: list[dict[str, Any]], model: str | None = None) -> AgentResult:
        convo = _with_system_prompt(messages)
        tools = self.registry.tools or None
        traces: list[ToolTrace] = []
        last_content = ""

        for rnd in range(1, self.max_rounds + 1):
            try:
                resp = await self.ollama.chat(convo, tools=tools, model=model)
            except OllamaError as e:
                return AgentResult(content=f"⚠️ {e}", traces=traces, rounds=rnd)

            if not resp.wants_tools:
                return AgentResult(content=resp.content or "(boş cevap)", traces=traces, rounds=rnd)

            last_content = resp.content
            # Modelin tool_call mesajını geçmişe ekle (Ollama formatı)
            convo.append(resp.raw_message or {"role": "assistant", "content": "", "tool_calls": []})

            for call in resp.tool_calls:
                log.info("Tur %d: %s(%s)", rnd, call.name, json.dumps(call.arguments, ensure_ascii=False))
                result = await self.registry.call(call.name, call.arguments)
                traces.append(ToolTrace(call.name, call.arguments, result))
                convo.append({"role": "tool", "tool_name": call.name, "content": result})

        # Tur sınırı aşıldı: tool sonuçlarıyla, tool'suz son bir cevap iste
        log.warning("MAX_TOOL_ROUNDS (%d) aşıldı, tool'suz son cevap isteniyor", self.max_rounds)
        try:
            resp = await self.ollama.chat(convo, tools=None, model=model)
            content = resp.content or last_content
        except OllamaError as e:
            content = f"⚠️ {e}"
        return AgentResult(content=content or "(cevap üretilemedi)", traces=traces, rounds=self.max_rounds)


def _with_system_prompt(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    msgs = [dict(m) for m in messages]
    if msgs and msgs[0].get("role") == "system":
        msgs[0]["content"] = SYSTEM_PROMPT + "\n\n" + str(msgs[0].get("content", ""))
        return msgs
    return [{"role": "system", "content": SYSTEM_PROMPT}, *msgs]
