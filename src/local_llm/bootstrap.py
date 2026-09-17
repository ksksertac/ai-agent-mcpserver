"""Otomatik kurulum & başlatma. Ajan açılırken çalışır; kullanıcı hiçbir şeyi elle kurmaz.

Adımlar (hepsi idempotent, hata ajanı düşürmez):
1. Ollama kurulu mu → değilse winget ile kur (Windows)
2. Ollama servisi ayakta mı → değilse `ollama serve` detached başlat, bekle
3. Model indirilmiş mi → değilse pull
4. Warm-up (VRAM'e yükle)
5. .vscode/settings.json'a customOAIModels girdisi yaz (eski yöntem)
6. VS Code profilindeki chatLanguageModels.json'a "Custom Endpoint" girdisi yaz (yeni yöntem)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from local_llm.config import PROJECT_ROOT, settings
from local_llm.ollama_client import OllamaClient, OllamaError

log = logging.getLogger("local_llm.bootstrap")


async def ensure_ready(ollama: OllamaClient) -> dict[str, Any]:
    report: dict[str, Any] = {}
    steps = (
        ("ollama_installed", _ensure_ollama_installed),
        ("ollama_running", lambda: _ensure_ollama_running(ollama)),
        ("model_ready", lambda: _ensure_model(ollama)),
        ("warm_up", lambda: _warm_up(ollama)),
        ("vscode_settings", _ensure_vscode_settings),
        ("vscode_models", _ensure_vscode_chat_models),
    )
    for name, step in steps:
        try:
            result = step()
            if asyncio.iscoroutine(result):
                result = await result
            report[name] = result
        except Exception as e:  # her adım bağımsız; biri düşerse diğerleri denenir
            log.error("bootstrap[%s] hata: %s", name, e)
            report[name] = f"HATA: {e}"
    return report


# ---------------------------------------------------------------- 1. kurulum


def ollama_binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    # winget kurulumundan sonra PATH güncellenmemiş olabilir
    if platform.system() == "Windows":
        cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
        if cand.exists():
            return str(cand)
    return None


def _ensure_ollama_installed() -> str:
    if ollama_binary():
        return "kurulu"
    if platform.system() != "Windows":
        raise RuntimeError("Ollama kurulu değil. https://ollama.com/download adresinden kurun.")
    if not shutil.which("winget"):
        raise RuntimeError(
            "Ollama ve winget yok. https://ollama.com/download adresinden elle kurun."
        )
    log.info("Ollama kurulu değil, winget ile kuruluyor (birkaç dakika sürebilir)...")
    subprocess.run(
        [
            "winget",
            "install",
            "-e",
            "--id",
            "Ollama.Ollama",
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        check=True,
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    if not ollama_binary():
        raise RuntimeError(
            "winget kurulumu bitti ama ollama bulunamadı; terminali yeniden açıp tekrar deneyin."
        )
    return "winget ile kuruldu"


# ---------------------------------------------------------------- 2. servis


async def _ensure_ollama_running(ollama: OllamaClient) -> str:
    if await ollama.is_alive():
        return "çalışıyor"
    binary = ollama_binary()
    if not binary:
        raise RuntimeError("ollama bulunamadı")
    log.info("Ollama servisi başlatılıyor: %s serve", binary)
    flags = 0
    if platform.system() == "Windows":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen(
        [binary, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=flags,
        start_new_session=(platform.system() != "Windows"),
    )
    deadline = time.monotonic() + settings.ollama_start_timeout
    while time.monotonic() < deadline:
        await asyncio.sleep(1)
        if await ollama.is_alive():
            return "başlatıldı"
    raise RuntimeError(f"Ollama {settings.ollama_start_timeout:.0f} sn içinde ayağa kalkmadı")


# ---------------------------------------------------------------- 3. model


async def _ensure_model(ollama: OllamaClient) -> str:
    if await ollama.has_model():
        return f"{ollama.model} indirilmiş"
    await ollama.pull()
    return f"{ollama.model} indirildi"


# ---------------------------------------------------------------- 4. warm-up


async def _warm_up(ollama: OllamaClient) -> str:
    t0 = time.perf_counter()
    try:
        await ollama.warm_up()
    except OllamaError as e:
        return f"atlandı: {e}"
    return f"{(time.perf_counter() - t0):.1f} sn"


# ---------------------------------------------------------------- 5. VS Code

CUSTOM_OAI_KEY = "github.copilot.chat.customOAIModels"


def vscode_model_entry() -> dict[str, Any]:
    return {
        "name": "Local Agent (Ollama + MCP)",
        "url": f"http://{settings.agent_host}:{settings.agent_port}/v1",
        "toolCalling": False,
        "vision": False,
        "thinking": False,
        "maxInputTokens": 32000,
        "maxOutputTokens": 4096,
    }


def _ensure_vscode_settings() -> str:
    path = PROJECT_ROOT / ".vscode" / "settings.json"
    path.parent.mkdir(exist_ok=True)
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8") or "{}")
        except json.JSONDecodeError:
            return f"atlandı: {path} geçerli JSON değil (elle düzeltin)"
    models = data.setdefault(CUSTOM_OAI_KEY, {})
    if settings.agent_model_name in models:
        return "zaten var"
    models[settings.agent_model_name] = vscode_model_entry()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return f"{path.relative_to(PROJECT_ROOT)} yazıldı"


# ------------------------------------------------ 6. VS Code chatLanguageModels.json


def vscode_chat_models_path() -> Path | None:
    """VS Code 1.10x+ 'Language Models → Add Models → Custom Endpoint' bu dosyaya yazar."""
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", ""))
    elif platform.system() == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    if not base.exists():
        return None
    return base / "Code" / "User" / "chatLanguageModels.json"


def vscode_chat_models_entry() -> dict[str, Any]:
    m = vscode_model_entry()
    return {
        "name": settings.agent_model_name,
        "vendor": "customendpoint",
        "apiType": "chat-completions",
        "models": [
            {
                "id": settings.agent_model_name,
                "name": m["name"],
                "url": m["url"],
                "toolCalling": False,
                "vision": False,
                "maxInputTokens": m["maxInputTokens"],
                "maxOutputTokens": m["maxOutputTokens"],
            }
        ],
    }


def _ensure_vscode_chat_models() -> str:
    path = vscode_chat_models_path()
    if path is None:
        return "atlandı: VS Code kullanıcı klasörü yok"
    data: list[dict[str, Any]] = []
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8") or "[]")
            data = raw if isinstance(raw, list) else []
        except json.JSONDecodeError:
            return f"atlandı: {path} geçerli JSON değil (elle düzeltin)"
    for group in data:
        if group.get("name") == settings.agent_model_name:
            ids = {m.get("id") for m in group.get("models", [])}
            if settings.agent_model_name in ids:
                return "zaten var"
            group.setdefault("models", []).append(vscode_chat_models_entry()["models"][0])
            break
    else:
        data.append(vscode_chat_models_entry())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    return f"{path} yazıldı"
