"""Ajanın MCP client tarafı: MCP sunucularını başlatır, tool listesini toplar, tool çağırır.

Ajan ↔ MCP Server iletişimi MCP protokolüdür (stdio, JSON-RPC): tools/list ve tools/call.
"""

from __future__ import annotations

import logging
import time
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from local_llm.config import settings

log = logging.getLogger("local_llm.agent.mcp")


class MCPToolRegistry:
    """Birden fazla MCP sunucusunu yönetir; tool adı → (session) eşlemesi tutar."""

    def __init__(self, specs: list[tuple[str, list[str]]] | None = None):
        self.specs = specs if specs is not None else settings.mcp_server_specs()
        self._stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tool_owner: dict[str, str] = {}
        self.tools: list[dict[str, Any]] = []  # Ollama formatında
        self.errors: dict[str, str] = {}

    async def start(self) -> None:
        for name, cmd in self.specs:
            try:
                await self._connect(name, cmd)
            except Exception as e:  # sunucu düşse bile ajan ayağa kalksın
                log.error("MCP sunucusu '%s' başlatılamadı: %s", name, e)
                self.errors[name] = str(e)
        log.info("MCP tool'ları hazır: %s", [t["function"]["name"] for t in self.tools])

    async def _connect(self, name: str, cmd: list[str]) -> None:
        params = StdioServerParameters(command=cmd[0], args=cmd[1:])
        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()
        self._sessions[name] = session
        result = await session.list_tools()
        for t in result.tools:
            if t.name in self._tool_owner:
                log.warning("Tool adı çakışıyor, atlandı: %s (%s)", t.name, name)
                continue
            self._tool_owner[t.name] = name
            self.tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.input_schema or {"type": "object", "properties": {}},
                    },
                }
            )
        log.info("MCP '%s' bağlandı: %d tool", name, len(result.tools))

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        owner = self._tool_owner.get(name)
        if owner is None:
            return f"HATA: '{name}' adında bir tool yok. Mevcut: {', '.join(self._tool_owner)}"
        t0 = time.perf_counter()
        try:
            result = await self._sessions[owner].call_tool(name, arguments)
        except Exception as e:
            log.exception("tool %s hata", name)
            return f"HATA: {name} çalıştırılamadı: {e}"
        ms = (time.perf_counter() - t0) * 1000
        text = _result_text(result)
        log.info("🔧 %s(%s) → %d karakter, %.0f ms", name, arguments, len(text), ms)
        return text

    async def close(self) -> None:
        await self._stack.aclose()


def _result_text(result: Any) -> str:
    parts: list[str] = []
    for c in getattr(result, "content", []) or []:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
    if getattr(result, "is_error", False):
        return "HATA: " + ("\n".join(parts) or "bilinmeyen hata")
    return "\n".join(parts) if parts else "(boş sonuç)"
