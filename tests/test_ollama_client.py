import json

import httpx
import pytest
import respx

from local_llm.ollama_client import OllamaClient, OllamaError, strip_think

HOST = "http://ollama.test"


@pytest.fixture
async def client():
    c = OllamaClient(host=HOST, model="qwen3:4b", timeout=5)
    yield c
    await c.aclose()


def test_strip_think():
    assert strip_think("<think>hmm\nhmm</think>\nCevap") == "Cevap"
    assert strip_think("düz") == "düz"
    assert strip_think("düşünüyorum...\n</think>\n\nCevap") == "Cevap"


@respx.mock
async def test_chat_duz_cevap(client):
    respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(
            200, json={"message": {"role": "assistant", "content": "<think>x</think>Merhaba!"}}
        )
    )
    r = await client.chat([{"role": "user", "content": "selam"}])
    assert r.content == "Merhaba!" and not r.wants_tools


@respx.mock
async def test_chat_tool_call(client):
    route = respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"function": {"name": "sistem_bilgisi", "arguments": {}}}],
                }
            },
        )
    )
    tools = [
        {
            "type": "function",
            "function": {"name": "sistem_bilgisi", "description": "x", "parameters": {}},
        }
    ]
    r = await client.chat([{"role": "user", "content": "saat kaç"}], tools=tools)
    assert r.wants_tools and r.tool_calls[0].name == "sistem_bilgisi"
    body = json.loads(route.calls[0].request.content)
    assert body["tools"] == tools and body["stream"] is False and "think" not in body


@respx.mock
async def test_tool_call_string_arguments(client):
    respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(
            200,
            json={
                "message": {
                    "content": "",
                    "tool_calls": [
                        {"function": {"name": "dosya_ara", "arguments": '{"desen": "*.py"}'}}
                    ],
                }
            },
        )
    )
    r = await client.chat([])
    assert r.tool_calls[0].arguments == {"desen": "*.py"}


@respx.mock
async def test_list_models_ve_has_model(client):
    respx.get(f"{HOST}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
    )
    assert await client.list_models() == ["qwen3:4b"]
    assert await client.has_model("qwen3:4b")
    assert not await client.has_model("llama3:8b")


@respx.mock
async def test_ollama_kapali(client):
    respx.post(f"{HOST}/api/chat").mock(side_effect=httpx.ConnectError("boom"))
    with pytest.raises(OllamaError, match="ollama serve"):
        await client.chat([])


@respx.mock
async def test_model_yok(client):
    respx.post(f"{HOST}/api/chat").mock(
        return_value=httpx.Response(404, text='{"error":"model not found"}')
    )
    with pytest.raises(OllamaError, match="ollama pull"):
        await client.chat([])


@respx.mock
async def test_is_alive_kapali(client):
    respx.get(f"{HOST}/api/tags").mock(side_effect=httpx.ConnectError("x"))
    assert not await client.is_alive()


@pytest.mark.integration
async def test_gercek_ollama_tool_calling():
    """Gerçek Ollama: 'saat kaç?' → tool_calls dönmeli."""
    c = OllamaClient()
    if not await c.is_alive():
        pytest.skip("Ollama çalışmıyor")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "sistem_bilgisi",
                "description": "Saat, tarih veya sistem bilgisi sorulduğunda kullan.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    r = await c.chat([{"role": "user", "content": "saat kaç?"}], tools=tools)
    await c.aclose()
    assert r.wants_tools and r.tool_calls[0].name == "sistem_bilgisi"
