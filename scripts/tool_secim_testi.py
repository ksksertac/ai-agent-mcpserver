"""Tool seçim testi: model, alakalı sorularda tool çağırıyor mu, alakasızlarda çağırmıyor mu?

Kullanım:  uv run python scripts/tool_secim_testi.py [model1 model2 ...]
Gerçek Ollama + gerçek MCP sunucusu (tool listesi oradan alınır) gerekir.
"""

from __future__ import annotations

import asyncio
import sys
import time

from local_llm.agent.mcp_client import MCPToolRegistry
from local_llm.agent.prompts import SYSTEM_PROMPT
from local_llm.ollama_client import OllamaClient

# (soru, beklenen tool adı ya da None)
CASES: list[tuple[str, str | None]] = [
    ("saat kaç?", "sistem_bilgisi"),
    ("bugün günlerden ne?", "sistem_bilgisi"),
    ("RAM ne kadar dolu?", "sistem_bilgisi"),
    ("diskte ne kadar boş yer var?", "sistem_bilgisi"),
    ("projede hangi py dosyaları var?", "dosya_ara"),
    ("README dosyası nerede?", "dosya_ara"),
    ("pyproject.toml içinde ne yazıyor?", "dosya_oku"),
    ("not al: toplantı yarın 10'da", "not_kaydet"),
    ("şunu kaydet: şifreyi değiştir", "not_kaydet"),
    ("notlarım neler?", "notlari_getir"),
    ("Python'da liste nasıl sıralanır?", None),
    ("2+2 kaç?", None),
    ("Türkiye'nin başkenti neresi?", None),
    ("merhaba nasılsın?", None),
    ("bana bir fıkra anlat", None),
    ("HTTP 404 ne demek?", None),
    ("git commit nasıl geri alınır?", None),
    ("İstanbul'un nüfusu kaç?", None),
    ("bir haiku yaz", None),
    ("JSON nedir?", None),
]


async def run_model(model: str, tools: list[dict]) -> None:
    ollama = OllamaClient(model=model)
    ok = 0
    t0 = time.perf_counter()
    print(f"\n=== {model} ===")
    for q, expected in CASES:
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": q}]
        r = await ollama.chat(msgs, tools=tools)
        got = r.tool_calls[0].name if r.wants_tools else None
        hit = got == expected
        ok += hit
        print(f"  {'✓' if hit else '✗'} {q:<40} beklenen={expected!s:<15} gelen={got}")
    dt = time.perf_counter() - t0
    print(
        f"  → {ok}/{len(CASES)} isabet (%{ok * 100 // len(CASES)}), {dt / len(CASES):.1f} sn/soru"
    )
    await ollama.aclose()


async def main() -> None:
    models = sys.argv[1:] or ["qwen3:4b"]
    reg = MCPToolRegistry()
    await reg.start()
    try:
        for m in models:
            await run_model(m, reg.tools)
    finally:
        await reg.close()


if __name__ == "__main__":
    asyncio.run(main())
