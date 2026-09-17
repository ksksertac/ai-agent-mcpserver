"""MCP Server — "eller". Tool'ları barındırır; kim çağırırsa çalıştırır. Ollama'yı ÇAĞIRMAZ.

Çalıştırma: `uv run local-mcp` (stdio). Loglar stderr'e; stdout MCP protokolüne aittir.
"""

import logging

from mcp.server.mcpserver import MCPServer

from local_llm.logging_setup import setup_logging
from local_llm.mcp_server.tools.files import dosya_ara, dosya_oku
from local_llm.mcp_server.tools.mock import (
    docker_listele,
    dokuman_ara,
    musteri_faturasi,
    siparisleri_getir,
    son_commit,
    takvim_bugun,
)
from local_llm.mcp_server.tools.notes import not_kaydet, notlari_getir
from local_llm.mcp_server.tools.system import sistem_bilgisi

log = logging.getLogger("local_llm.mcp_server")

mcp = MCPServer(
    "local-tools",
    instructions=(
        "Yerel makine için araçlar: sistem bilgisi, dosya arama/okuma, not alma. "
        "Ayrıca sözde (mock) iş araçları: sipariş, fatura, doküman, git, docker, takvim."
    ),
)

# Docstring'ler tool açıklaması olarak LLM'e gider — "NE ZAMAN KULLAN / KULLANMA" formatı korunmalı.
GERCEK_TOOLS = (sistem_bilgisi, dosya_ara, dosya_oku, not_kaydet, notlari_getir)
MOCK_TOOLS = (
    siparisleri_getir,
    musteri_faturasi,
    dokuman_ara,
    son_commit,
    docker_listele,
    takvim_bugun,
)

for fn in (*GERCEK_TOOLS, *MOCK_TOOLS):
    mcp.tool()(fn)


def main() -> None:
    setup_logging()
    log.info("MCP server 'local-tools' stdio üzerinde başlıyor")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
