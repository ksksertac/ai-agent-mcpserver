"""Ajan HTTP sunucusu — VS Code Chat buraya bağlanır.

OpenAI-uyumlu:  POST /v1/chat/completions, GET /v1/models
Ollama-uyumlu (yedek plan): POST /api/chat, GET /api/tags, GET /api/version
Sağlık:         GET /health
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

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
        settings.agent_host, settings.agent_port, settings.ollama_model, len(state.registry.tools),
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
        "data": [{"id": settings.agent_model_name, "object": "model", "created": 0, "owned_by": "local"}],
    }


@app.post("/v1/chat/completions")
async def v1_chat(request: Request):
    body = await request.json()
    messages = _normalize_messages(body.get("messages", []))
    result = await state.loop.run(messages)
    content = _decorate(result)
    if body.get("stream"):
        return StreamingResponse(_sse_openai(content, body.get("model")), media_type="text/event-stream")
    return _openai_response(content, body.get("model"))


def _openai_response(content: str, model: str | None) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or settings.agent_model_name,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


async def _sse_openai(content: str, model: str | None):
    cid = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    base = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model or settings.agent_model_name}
    first = {**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": ""}, "finish_reason": None}]}
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
    return {"models": [{"name": settings.agent_model_name, "model": settings.agent_model_name, "size": 0, "details": {}}]}


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
        return StreamingResponse(_ndjson_ollama(content, body.get("model")), media_type="application/x-ndjson")
    return {"model": body.get("model"), "message": {"role": "assistant", "content": content}, "done": True}


async def _ndjson_ollama(content: str, model: str | None):
    for chunk in _chunks(content, 80):
        yield json.dumps({"model": model, "message": {"role": "assistant", "content": chunk}, "done": False}, ensure_ascii=False) + "\n"
    yield json.dumps({"model": model, "message": {"role": "assistant", "content": ""}, "done": True}) + "\n"


# ---------------------------------------------------------------- ortak

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
    return JSONResponse(status_code=500, content={"error": {"message": str(exc), "type": "server_error"}})


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """OpenAI content-parts formatını düz metne çevir; sadece role/content taşı."""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "user")
        if role not in ("system", "user", "assistant"):
            continue
        content = m.get("content", "")
        if isinstance(content, list):
            content = "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
        out.append({"role": role, "content": content or ""})
    return out


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
    parser.add_argument("--no-bootstrap", action="store_true", help="Ollama kurulum/başlatma adımlarını atla")
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
