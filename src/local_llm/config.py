"""Uygulama ayarları. Tümü env ile override edilebilir (ör. OLLAMA_MODEL=qwen3:8b)."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout: float = 120.0
    ollama_think: bool | None = None  # None: Ollama varsayılanı (qwen3 düşünür ama ayrı alanda)

    # Ajan
    agent_host: str = "127.0.0.1"
    agent_port: int = 8000
    agent_model_name: str = "local-agent"  # VS Code'da görünen model adı
    max_tool_rounds: int = 5

    # MCP sunucuları: her biri "isim=komut arg1 arg2" formatında, ';' ile ayrılır.
    # Varsayılan: bizim MCP sunucumuz, aynı venv içindeki python ile.
    mcp_servers: str = f"local-tools={sys.executable} -m local_llm.mcp_server.server"

    # Bootstrap
    bootstrap: bool = True
    ollama_start_timeout: float = 30.0

    # Notlar (demo tool) nereye yazılır
    notes_file: Path = PROJECT_ROOT / ".notes.json"

    def mcp_server_specs(self) -> list[tuple[str, list[str]]]:
        specs: list[tuple[str, list[str]]] = []
        for item in self.mcp_servers.split(";"):
            item = item.strip()
            if not item:
                continue
            name, _, cmd = item.partition("=")
            specs.append((name.strip(), cmd.split()))
        return specs


settings = Settings()
