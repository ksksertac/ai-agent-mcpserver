"""Ajan döngüsü: sahte Ollama (respx) + sahte MCP registry."""

import json

import httpx
import pytest
import respx

from local_llm.agent.loop import AgentLoop
from local_llm.agent.mcp_client import MCPToolRegistry
from local_llm.ollama_client import OllamaClient

HOST = "http://ollama.test"


class FakeRegistry(MCPToolRegistry):
    def __init__(self):
        super().__init__(specs=[])
        self.tools = [
            {"type": "function", "function": {"name": "sistem_bilgisi", "description": "saat", "parameters": {}}}
        ]
        self.calls: list[tuple[str, dict]] = []

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        return f"SONUC({name})"


def _msg(content="", tool_calls=None):
    m = {"role": "assistant", "content": content}
    if tool_calls:
        m["tool_calls"] = [{"function": {"name": n, "arguments": a}} for n, a in tool_calls]
    return httpx.Response(200, json={"message": m})


@pytest.fixture
async def setup():
    ollama = OllamaClient(host=HOST, model="m", timeout=5)
    reg = FakeRegistry()
    loop = AgentLoop(ollama, reg, max_rounds=3)
    yield ollama, reg, loop
    await ollama.aclose()


@respx.mock
async def test_duz_cevap_tool_cagirmaz(setup):
    ollama, reg, loop = setup
    route = respx.post(f"{HOST}/api/chat").mock(return_value=_msg("Merhaba!"))
    r = await loop.run([{"role": "user", "content": "selam"}])
    assert r.content == "Merhaba!" and r.traces == [] and reg.calls == []
    body = json.loads(route.calls[0].request.content)
    assert body["messages"][0]["role"] == "system"  # system prompt eklendi
    assert body["tools"][0]["function"]["name"] == "sistem_bilgisi"  # tool listesi gönderildi


@respx.mock
async def test_tek_tool_turu(setup):
    ollama, reg, loop = setup
    route = respx.post(f"{HOST}/api/chat").mock(
        side_effect=[_msg(tool_calls=[("sistem_bilgisi", {})]), _msg("Saat 14:00")]
    )
    r = await loop.run([{"role": "user", "content": "saat kaç"}])
    assert r.content == "Saat 14:00"
    assert reg.calls == [("sistem_bilgisi", {})]
    assert [t.name for t in r.traces] == ["sistem_bilgisi"]
    # ikinci istekte tool sonucu role:tool olarak gitmiş olmalı
    second = json.loads(route.calls[1].request.content)
    assert second["messages"][-1] == {"role": "tool", "tool_name": "sistem_bilgisi", "content": "SONUC(sistem_bilgisi)"}


@respx.mock
async def test_coklu_tur(setup):
    ollama, reg, loop = setup
    respx.post(f"{HOST}/api/chat").mock(
        side_effect=[
            _msg(tool_calls=[("sistem_bilgisi", {})]),
            _msg(tool_calls=[("sistem_bilgisi", {"x": 1})]),
            _msg("bitti"),
        ]
    )
    r = await loop.run([{"role": "user", "content": "?"}])
    assert r.content == "bitti" and len(reg.calls) == 2 and r.rounds == 3


@respx.mock
async def test_max_rounds_asilinca_toolsuz_son_cevap(setup):
    ollama, reg, loop = setup
    route = respx.post(f"{HOST}/api/chat").mock(
        side_effect=[_msg(tool_calls=[("sistem_bilgisi", {})])] * 3 + [_msg("son cevap")]
    )
    r = await loop.run([{"role": "user", "content": "?"}])
    assert r.content == "son cevap" and len(reg.calls) == 3
    last = json.loads(route.calls[-1].request.content)
    assert "tools" not in last  # son istek tool'suz


@respx.mock
async def test_ollama_kapaliysa_anlasilir_mesaj(setup):
    ollama, reg, loop = setup
    respx.post(f"{HOST}/api/chat").mock(side_effect=httpx.ConnectError("x"))
    r = await loop.run([{"role": "user", "content": "?"}])
    assert "ollama serve" in r.content


async def test_bilinmeyen_tool_hata_metni():
    reg = MCPToolRegistry(specs=[])
    out = await reg.call("yok", {})
    assert out.startswith("HATA")
