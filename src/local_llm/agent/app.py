"""Ajan HTTP sunucusu — VS Code Chat buraya bağlanır.

OpenAI-uyumlu:  POST /v1/chat/completions, GET /v1/models
Ollama-uyumlu (yedek plan): POST /api/chat, GET /api/tags, GET /api/version
Sağlık:         GET /health
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from local_llm import bootstrap
from local_llm.agent.loop import AgentLoop, AgentResult
from local_llm.agent.mcp_client import MCPToolRegistry
from local_llm.config import settings
from local_llm.logging_setup import setup_logging
from local_llm.ollama_client import OllamaClient

log = logging.getLogger("local_llm.agent")


class State:
    ollama: OllamaClient
    registry: MCPToolRegistry
    loop: AgentLoop
    bootstrap_report: dict[str, Any] = {}


state = State()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    state.ollama = OllamaClient()
    if settings.bootstrap:
        state.bootstrap_report = await bootstrap.ensure_ready(state.ollama)
    state.registry = MCPToolRegistry()
    await state.registry.start()
    state.loop = AgentLoop(state.ollama, state.registry)
    log.info(
        "Ajan hazır → http://%s:%d  (model: %s, %d tool). VS Code'da '%s' modelini seçin.",
        settings.agent_host,
        settings.agent_port,
        settings.ollama_model,
        len(state.registry.tools),
        settings.agent_model_name,
    )
    try:
        yield
    finally:
        await state.registry.close()
        await state.ollama.aclose()


app = FastAPI(title="Local Agent", lifespan=lifespan)


# ---------------------------------------------------------------- OpenAI uyumlu


@app.get("/v1/models")
async def v1_models():
    return {
        "object": "list",
        "data": [
            {"id": settings.agent_model_name, "object": "model", "created": 0, "owned_by": "local"}
        ],
    }


@app.post("/v1/chat/completions")
async def v1_chat(request: Request):
    body = await request.json()
    _dump_request(body)
    messages = _normalize_messages(body.get("messages", []))
    result = await state.loop.run(messages)
    content = _decorate(result)
    if body.get("stream"):
        return StreamingResponse(
            _sse_openai(content, body.get("model")), media_type="text/event-stream"
        )
    return _openai_response(content, body.get("model"))


def _openai_response(content: str, model: str | None) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or settings.agent_model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _sse_openai(content: str, model: str | None):
    cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    base = {
        "id": cid,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model or settings.agent_model_name,
    }
    first = {
        **base,
        "choices": [
            {"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}
        ],
    }
    yield f"data: {json.dumps(first)}\n\n"
    # cevabı parça parça gönder (istemci akış gibi görsün)
    for chunk in _chunks(content, 80):
        d = {**base, "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}]}
        yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
    done = {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
    yield f"data: {json.dumps(done)}\n\n"
    yield "data: [DONE]\n\n"


# ---------------------------------------------------------------- Ollama uyumlu (yedek)


@app.get("/api/version")
async def api_version():
    return {"version": "0.1.0-local-agent"}


@app.get("/api/tags")
async def api_tags():
    return {
        "models": [
            {
                "name": settings.agent_model_name,
                "model": settings.agent_model_name,
                "size": 0,
                "details": {},
            }
        ]
    }


@app.post("/api/show")
async def api_show():
    return {"capabilities": ["completion"], "details": {}, "model_info": {}}


@app.post("/api/chat")
async def api_chat(request: Request):
    body = await request.json()
    messages = _normalize_messages(body.get("messages", []))
    result = await state.loop.run(messages)
    content = _decorate(result)
    if body.get("stream", True):
        return StreamingResponse(
            _ndjson_ollama(content, body.get("model")), media_type="application/x-ndjson"
        )
    return {
        "model": body.get("model"),
        "message": {"role": "assistant", "content": content},
        "done": True,
    }


async def _ndjson_ollama(content: str, model: str | None):
    for chunk in _chunks(content, 80):
        yield (
            json.dumps(
                {"model": model, "message": {"role": "assistant", "content": chunk}, "done": False},
                ensure_ascii=False,
            )
            + "\n"
        )
    yield (
        json.dumps({"model": model, "message": {"role": "assistant", "content": ""}, "done": True})
        + "\n"
    )


# ---------------------------------------------------------------- ortak


@app.get("/", response_class=HTMLResponse)
async def index():
    tools = "".join(f"<li><code>{t['function']['name']}</code></li>" for t in state.registry.tools)
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Local Agent</title>
<style>body{{font-family:system-ui;max-width:720px;margin:40px auto;padding:0 16px;line-height:1.5}}
code{{background:#eee;padding:1px 5px;border-radius:3px}}</style></head><body>
<h1>🤖 Local Agent çalışıyor</h1>
<p>Model: <code>{settings.ollama_model}</code> · MCP tool sayısı:
<b>{len(state.registry.tools)}</b></p>
<p>VS Code → Copilot Chat → model seçici → <b>Local Agent (Ollama + MCP)</b> seçip soru sorun.</p>
<ul>
<li><a href="/health">/health</a> — durum</li>
<li><a href="/v1/models">/v1/models</a> — VS Code'un gördüğü model</li>
<li><a href="/docs">/docs</a> — API dokümanı</li>
</ul>
<h3>Tool'lar</h3><ul>{tools}</ul>
</body></html>"""


@app.get("/health")
async def health():
    return {
        "ok": True,
        "ollama": await state.ollama.is_alive(),
        "model": settings.ollama_model,
        "tools": [t["function"]["name"] for t in state.registry.tools],
        "mcp_errors": state.registry.errors,
        "bootstrap": state.bootstrap_report,
    }


@app.exception_handler(Exception)
async def on_error(_: Request, exc: Exception):
    log.exception("istek hatası")
    return JSONResponse(
        status_code=500, content={"error": {"message": str(exc), "type": "server_error"}}
    )


# Copilot Chat kullanıcı mesajını sarmalar: <context>…</context><attachments>…</attachments>
# <reminderInstructions>…</reminderInstructions><userRequest>ASIL SORU</userRequest>
_USER_REQUEST_RE = re.compile(r"<userRequest>\s*(.*?)\s*</userRequest>", re.S)
_ATTACHMENTS_RE = re.compile(r"<attachments>\s*(.*?)\s*</attachments>", re.S)


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI content-parts formatını düz metne çevir; sadece role/content taşı.

    - İstemci system mesajları varsayılan olarak atılır (settings.keep_client_system):
      Copilot'un agent-mode prompt'u binlerce token, 4B modelin tool seçimini bozuyor.
    - Copilot sarmalı varsa sadece <userRequest> (+ varsa <attachments>) alınır.
    """
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        if role not in ("system", "user", "assistant"):
            continue
        if role == "system" and not settings.keep_client_system:
            continue
        content = m.get("content", "")
        if isinstance(content, list):
            content = "\n".join(
                p.get("text", "")
                for p in content
                if isinstance(p, dict) and p.get("type") == "text"
            )
        content = content or ""
        if role == "user":
            content = _unwrap_copilot_user(content)
        out.append({"role": role, "content": content})
    return out


def _unwrap_copilot_user(content: str) -> str:
    req = _USER_REQUEST_RE.search(content)
    if not req:
        return content
    text = req.group(1)
    att = _ATTACHMENTS_RE.search(content)
    if att and att.group(1):
        text = f"{text}\n\n[Ekli içerik]\n{att.group(1)}"
    return text


def _dump_request(body: dict[str, Any]) -> None:
    """Son isteği dosyaya yaz (debug: istemci ne gönderiyor?)."""
    path = settings.dump_last_request
    if not path:
        return
    try:
        path.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:  # debug kolaylığı; ajanı düşürmesin
        log.warning("istek dökümü yazılamadı: %s", e)


def _decorate(result: AgentResult) -> str:
    if not result.traces:
        return result.content
    used = ", ".join(f"`{t.name}`" for t in result.traces)
    return f"{result.content}\n\n---\n🔧 Kullanılan araçlar: {used}"


def _chunks(text: str, n: int):
    for i in range(0, len(text), n):
        yield text[i : i + n]
    if not text:
        yield ""


# ---------------------------------------------------------------- CLI


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Agent (Ollama + MCP)")
    parser.add_argument(
        "--no-bootstrap", action="store_true", help="Ollama kurulum/başlatma adımlarını atla"
    )
    parser.add_argument("--check", action="store_true", help="Sadece bootstrap'ı çalıştır ve çık")
    parser.add_argument("--port", type=int, default=settings.agent_port)
    args = parser.parse_args()

    if args.no_bootstrap:
        settings.bootstrap = False
    if args.check:
        import asyncio

        setup_logging()

        async def _check():
            c = OllamaClient()
            report = await bootstrap.ensure_ready(c)
            await c.aclose()
            print(json.dumps(report, ensure_ascii=False, indent=2))

        asyncio.run(_check())
        return

    uvicorn.run(app, host=settings.agent_host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
