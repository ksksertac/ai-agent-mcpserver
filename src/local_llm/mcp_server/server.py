"""MCP Server — "eller". Tool'ları barındırır; kim çağırırsa çalıştırır. Ollama'yı ÇAĞIRMAZ.

Çalıştırma: `uv run local-mcp` (stdio). Loglar stderr'e; stdout MCP protokolüne aittir.
"""

import logging

from mcp.server.mcpserver import MCPServer

from local_llm.logging_setup import setup_logging
from local_llm.mcp_server.tools.files import dosya_ara, dosya_oku
from local_llm.mcp_server.tools.notes import not_kaydet, notlari_getir
from local_llm.mcp_server.tools.system import sistem_bilgisi

log = logging.getLogger("local_llm.mcp_server")

mcp = MCPServer(
    "local-tools",
    instructions="Yerel makine için araçlar: sistem bilgisi, dosya arama/okuma, not alma.",
)

# Docstring'ler tool açıklaması olarak LLM'e gider — "NE ZAMAN KULLAN / KULLANMA" formatı korunmalı.
for fn in (sistem_bilgisi, dosya_ara, dosya_oku, not_kaydet, notlari_getir):
    mcp.tool()(fn)


def main() -> None:
    setup_logging()
    log.info("MCP server 'local-tools' stdio üzerinde başlıyor")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
