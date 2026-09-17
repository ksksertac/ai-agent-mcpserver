"""Ollama HTTP istemcisi. Ajan ve bootstrap tarafından kullanılır.

Ollama sadece "beyin"dir: metin veya tool_calls üretir. Tool'ları çalıştıran ajandır.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from local_llm.config import settings

log = logging.getLogger("local_llm.ollama")

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class OllamaError(RuntimeError):
    """Kullanıcıya gösterilebilir, anlaşılır Ollama hatası."""


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict[str, Any] = field(default_factory=dict)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


def strip_think(text: str) -> str:
    """qwen3 gibi modellerin ürettiği <think>…</think> bloklarını temizler.

    Ollama bazen açılış etiketini yutup sadece `</think>` bırakıyor; o durumda son
    `</think>`'ten sonrası cevaptır.
    """
    text = _THINK_RE.sub("", text)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


class OllamaClient:
    def __init__(
        self, host: str | None = None, model: str | None = None, timeout: float | None = None
    ):
        self.host = (host or settings.ollama_host).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.ollama_timeout
        self._client = httpx.AsyncClient(base_url=self.host, timeout=self.timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    # ---- sağlık / modeller -------------------------------------------------

    async def is_alive(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=3.0)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[str]:
        r = await self._request("GET", "/api/tags")
        return [m["name"] for m in r.json().get("models", [])]

    async def has_model(self, model: str | None = None) -> bool:
        model = model or self.model
        names = await self.list_models()
        if model in names:
            return True
        if ":" not in model:
            return any(n.split(":")[0] == model for n in names)
        return False

    async def pull(self, model: str | None = None) -> None:
        """Modeli indirir; ilerlemeyi loglar (stream)."""
        model = model or self.model
        log.info("Model indiriliyor: %s", model)
        last = ""
        async with self._client.stream(
            "POST", "/api/pull", json={"model": model}, timeout=None
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line:
                    continue
                d = json.loads(line)
                if d.get("error"):
                    raise OllamaError(f"Model indirilemedi: {d['error']}")
                status = d.get("status", "")
                if "total" in d and "completed" in d:
                    pct = int(d["completed"] * 100 / max(d["total"], 1))
                    status = f"{status} %{pct}"
                if status != last:
                    log.info("  %s", status)
                    last = status
        log.info("Model hazır: %s", model)

    async def warm_up(self, model: str | None = None) -> None:
        """Modeli VRAM'e yükler ki ilk soru beklemesin."""
        await self._request(
            "POST",
            "/api/chat",
            json={"model": model or self.model, "messages": [], "keep_alive": "30m"},
        )

    # ---- sohbet --------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": "30m",
        }
        # think verilmezse Ollama düşünceyi ayrı `thinking` alanına koyar, content temiz gelir.
        # (qwen3:4b'de think=False düşünceyi kapatmıyor, content'e karıştırıyor.)
        if settings.ollama_think is not None:
            payload["think"] = settings.ollama_think
        if tools:
            payload["tools"] = tools
        if options:
            payload["options"] = options

        r = await self._request("POST", "/api/chat", json=payload)
        msg = r.json().get("message", {})
        calls = [
            ToolCall(
                name=tc["function"]["name"], arguments=_parse_args(tc["function"].get("arguments"))
            )
            for tc in msg.get("tool_calls", []) or []
        ]
        return ChatResponse(
            content=strip_think(msg.get("content", "") or ""), tool_calls=calls, raw_message=msg
        )

    # ---- iç -----------------------------------------------------------------

    async def _request(self, method: str, url: str, **kw: Any) -> httpx.Response:
        try:
            r = await self._client.request(method, url, **kw)
        except httpx.ConnectError as e:
            raise OllamaError(
                f"Ollama'ya bağlanılamadı ({self.host}). `ollama serve` çalışıyor mu?"
            ) from e
        except httpx.TimeoutException as e:
            raise OllamaError(
                f"Ollama zaman aşımı ({self.timeout}s). Model ilk yüklemede yavaş olabilir."
            ) from e
        if r.status_code == 404 and "model" in r.text.lower():
            raise OllamaError(
                f"Model bulunamadı: `ollama pull {self.model}` çalıştırın. ({r.text.strip()})"
            )
        if r.status_code >= 400:
            raise OllamaError(f"Ollama hatası {r.status_code}: {r.text.strip()[:300]}")
        return r


def _parse_args(args: Any) -> dict[str, Any]:
    if args is None:
        return {}
    if isinstance(args, str):
        try:
            return json.loads(args)
        except json.JSONDecodeError:
            return {"_raw": args}
    return dict(args)
