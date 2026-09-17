"""Bootstrap: subprocess/httpx mock ile. Gerçek winget/ollama çağrılmaz."""

import json

import httpx
import pytest
import respx

from local_llm import bootstrap
from local_llm.config import settings
from local_llm.ollama_client import OllamaClient

HOST = "http://ollama.test"


@pytest.fixture
async def ollama():
    c = OllamaClient(host=HOST, model="qwen3:4b", timeout=5)
    yield c
    await c.aclose()


@respx.mock
async def test_hersey_hazirsa_hicbir_sey_yapmaz(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "ollama_binary", lambda: "C:/ollama.exe")
    monkeypatch.setattr(bootstrap, "PROJECT_ROOT", tmp_path)
    respx.get(f"{HOST}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
    )
    respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(200, json={}))
    popen_called = []
    monkeypatch.setattr(bootstrap.subprocess, "Popen", lambda *a, **k: popen_called.append(a))

    report = await bootstrap.ensure_ready(ollama)

    assert report["ollama_installed"] == "kurulu"
    assert report["ollama_running"] == "çalışıyor"
    assert report["model_ready"].endswith("indirilmiş")
    assert popen_called == []
    settings_file = tmp_path / ".vscode" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert settings.agent_model_name in data[bootstrap.CUSTOM_OAI_KEY]


@respx.mock
async def test_servis_kapaliysa_baslatir(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "ollama_binary", lambda: "C:/ollama.exe")
    monkeypatch.setattr(bootstrap, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(settings, "ollama_start_timeout", 3)
    # ilk çağrı: kapalı, sonrakiler: açık
    tags = respx.get(f"{HOST}/api/tags")
    tags.side_effect = [httpx.ConnectError("x")] + [
        httpx.Response(200, json={"models": [{"name": "qwen3:4b"}]})
    ] * 10
    respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(200, json={}))
    popen_calls = []
    monkeypatch.setattr(bootstrap.subprocess, "Popen", lambda *a, **k: popen_calls.append(a[0]))

    report = await bootstrap.ensure_ready(ollama)

    assert popen_calls == [["C:/ollama.exe", "serve"]]
    assert report["ollama_running"] == "başlatıldı"


@respx.mock
async def test_model_yoksa_indirir(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "ollama_binary", lambda: "C:/ollama.exe")
    monkeypatch.setattr(bootstrap, "PROJECT_ROOT", tmp_path)
    respx.get(f"{HOST}/api/tags").mock(return_value=httpx.Response(200, json={"models": []}))
    respx.post(f"{HOST}/api/chat").mock(return_value=httpx.Response(200, json={}))
    pull = respx.post(f"{HOST}/api/pull").mock(
        return_value=httpx.Response(200, text='{"status":"pulling"}\n{"status":"success"}\n')
    )

    report = await bootstrap.ensure_ready(ollama)

    assert pull.called and report["model_ready"].endswith("indirildi")


@respx.mock
async def test_adim_hatasi_digerlerini_durdurmaz(ollama, monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "ollama_binary", lambda: None)  # kurulu değil
    monkeypatch.setattr(bootstrap.platform, "system", lambda: "Linux")  # winget yok → hata
    monkeypatch.setattr(bootstrap, "PROJECT_ROOT", tmp_path)
    respx.get(f"{HOST}/api/tags").mock(side_effect=httpx.ConnectError("x"))

    report = await bootstrap.ensure_ready(ollama)

    assert report["ollama_installed"].startswith("HATA")
    assert report["ollama_running"].startswith("HATA")
    assert "vscode_settings" in report  # son adım yine de çalıştı


def test_vscode_settings_mevcut_ayarlari_korur(monkeypatch, tmp_path):
    monkeypatch.setattr(bootstrap, "PROJECT_ROOT", tmp_path)
    vs = tmp_path / ".vscode"
    vs.mkdir()
    (vs / "settings.json").write_text('{"editor.fontSize": 14}', encoding="utf-8")

    assert bootstrap._ensure_vscode_settings().endswith("yazıldı")
    data = json.loads((vs / "settings.json").read_text(encoding="utf-8"))
    assert (
        data["editor.fontSize"] == 14
        and settings.agent_model_name in data[bootstrap.CUSTOM_OAI_KEY]
    )
    assert bootstrap._ensure_vscode_settings() == "zaten var"  # idempotent


def test_chat_models_json_yazilir_ve_idempotent(monkeypatch, tmp_path):
    target = tmp_path / "Code" / "User" / "chatLanguageModels.json"
    monkeypatch.setattr(bootstrap, "vscode_chat_models_path", lambda: target)

    assert bootstrap._ensure_vscode_chat_models().endswith("yazıldı")
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data[0]["vendor"] == "customendpoint"
    assert data[0]["models"][0]["id"] == settings.agent_model_name
    assert data[0]["models"][0]["url"].endswith(":8000/v1")
    assert bootstrap._ensure_vscode_chat_models() == "zaten var"


def test_chat_models_json_bos_alanlari_doldurmaz_baska_girdiyi_korur(monkeypatch, tmp_path):
    target = tmp_path / "chatLanguageModels.json"
    target.write_text('[{"name": "baska", "vendor": "openai", "models": []}]', encoding="utf-8")
    monkeypatch.setattr(bootstrap, "vscode_chat_models_path", lambda: target)

    bootstrap._ensure_vscode_chat_models()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert [g["name"] for g in data] == ["baska", settings.agent_model_name]
