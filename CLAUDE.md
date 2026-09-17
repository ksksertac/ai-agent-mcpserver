# Local LLM MCP Server

VS Code Chat'ten (Copilot Chat / Agent mode) çağrılan, arka planda **yerel bir LLM (Ollama)** ile konuşan Python MCP sunucusu. Amaç: VS Code'da soru sorulduğunda cevap buluttan değil, bizim MCP sunucumuz üzerinden yerel modelden ve **bizim belirlediğimiz formatta** gelsin.

> Kaldığın yerden devam etmek için: önce [tasks.md](tasks.md) dosyasına bak, `[ ]` olan ilk taska başla. Biten taskı `[x]` yap.

## Ortam (tespit edildi — 2026-09-17)

| Bileşen | Durum |
|---|---|
| OS | Windows 11 Pro, PowerShell |
| Python | 3.14.3 |
| Paket yöneticisi | `uv` 0.12.15 (venv + bağımlılık için bunu kullan) |
| Ollama | 0.34.0 kurulu, `http://localhost:11434` |
| İndirilmiş modeller | `qwen3:4b` (tool-calling destekler, **varsayılan**), `qwen2.5:3b`, `qwen2.5vl:3b` |
| GPU | RTX 4060 Laptop 8 GB VRAM → 4B–8B q4 modeller rahat çalışır |
| VS Code | 1.138.0 (MCP desteği yerleşik) |

## Mimari

```
┌──────────────────────┐   MCP (stdio, JSON-RPC)   ┌──────────────────────┐   HTTP /api/chat   ┌──────────────┐
│  VS Code Chat        │ ────────────────────────► │  local-llm-mcp       │ ─────────────────► │  Ollama      │
│  (Copilot Agent mode)│ ◄──────────────────────── │  (Python, FastMCP)   │ ◄───────────────── │  qwen3:4b    │
│  .vscode/mcp.json    │      tool result           │  tools / prompts /   │      answer        │  localhost   │
└──────────────────────┘                            │  resources           │                    │  :11434      │
                                                    └──────────────────────┘                    └──────────────┘
```

Akış:
1. Kullanıcı VS Code Chat'te soru sorar (Agent mode, `#ask_local_llm` ile veya otomatik tool seçimiyle).
2. VS Code, `.vscode/mcp.json`'daki sunucuyu **stdio** ile başlatır ve `ask_local_llm` tool'unu çağırır.
3. Sunucu; kullanıcı sorusunu **bizim system prompt + format şablonumuzla** sarar, Ollama `/api/chat`'e gönderir.
4. Ollama'dan gelen cevap istenen formata (Markdown / JSON / kısa-uzun / Türkçe) normalize edilip VS Code'a döner.

Opsiyonel (Faz 5): VS Code Chat'in kendi modelini de Ollama'ya çevirerek (Copilot Chat → Manage Models → Ollama) **tamamen yerel** bir döngü kurmak.

## Proje Yapısı (hedef)

```
mcpserver/
├── CLAUDE.md                  # bu dosya – proje hafızası
├── tasks.md                   # task listesi / ilerleme
├── pyproject.toml             # uv ile yönetilir, entry point: local-llm-mcp
├── .vscode/
│   └── mcp.json               # VS Code MCP sunucu tanımı
├── setup.ps1                  # tek komut kurulum: uv → uv sync → bootstrap
├── src/local_llm_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP app, tool/prompt/resource kayıtları, main()
│   ├── bootstrap.py           # ensure_ready(): Ollama kur/başlat, model çek, ısıt, mcp.json yaz
│   ├── config.py              # env/ayarlar: OLLAMA_HOST, MODEL, TIMEOUT, DEFAULT_STYLE
│   ├── ollama_client.py       # httpx ile /api/chat, /api/tags, /api/generate sarmalayıcı
│   ├── prompts.py             # system prompt şablonları ve cevap format kuralları
│   └── tools/
│       ├── ask.py             # ask_local_llm
│       ├── summarize.py       # summarize_text
│       ├── code.py            # explain_code / review_code
│       └── models.py          # list_models / set_model
└── tests/
    ├── test_ollama_client.py  # httpx mock ile
    └── test_tools.py
```

## Teknoloji Kararları

- **MCP SDK:** `mcp` (resmi Python SDK, `FastMCP` sınıfı). Transport: **stdio** (VS Code için en basit). İleride `streamable-http` eklenebilir.
- **LLM Runtime:** Ollama. Kendi sarmalayıcımız `httpx` ile yazılacak (resmi `ollama` paketi de kullanılabilir, ama bağımlılığı az tutmak için httpx tercih).
- **Varsayılan model:** `qwen3:4b` — tool-calling ve Türkçe desteği iyi, 8 GB VRAM'e sığar. `OLLAMA_MODEL` env ile değiştirilebilir.
- **Test:** `pytest` + `pytest-asyncio` + `respx` (httpx mock). Gerçek Ollama gerektiren testler `@pytest.mark.integration`.
- **Loglama:** stdio transport kullanıldığı için **stdout'a asla print etme** — MCP protokolünü bozar. Loglar `stderr`'e (`logging` + `StreamHandler(sys.stderr)`).

## MCP Sunucunun Sunacakları

**Tools**
| Tool | Girdi | Açıklama |
|---|---|---|
| `ask_local_llm` | `question: str`, `style: "kısa"\|"detaylı"\|"json"\|"markdown"` = "markdown", `system_prompt: str\|None`, `model: str\|None` | Ana tool. Soruyu yerel LLM'e iletir, formatlı cevap döner. |
| `summarize_text` | `text: str`, `max_sentences: int = 3` | Metin özetleme. |
| `explain_code` | `code: str`, `language: str\|None` | Kodu açıklar. |
| `review_code` | `code: str` | Bug/iyileştirme önerileri listesi döner. |
| `list_models` | – | Ollama'daki modelleri listeler. |

**Prompts** (VS Code'da `/` ile görünen şablonlar)
- `turkish_assistant` — Türkçe, kısa, madde madde cevap veren system prompt.
- `code_reviewer` — kod inceleme şablonu.

**Resources**
- `ollama://models` — mevcut modeller (JSON).
- `config://current` — aktif model ve ayarlar.

## Komutlar

```powershell
# kurulum
uv sync

# sunucuyu elle çalıştır (stdio – terminalden test için MCP Inspector kullan)
uv run local-llm-mcp

# MCP Inspector ile debug
npx @modelcontextprotocol/inspector uv run local-llm-mcp

# testler
uv run pytest
uv run pytest -m "not integration"   # Ollama olmadan

# Ollama
ollama serve            # servis çalışmıyorsa
ollama list
ollama pull qwen3:4b
```

## VS Code Entegrasyonu

`.vscode/mcp.json`:
```json
{
  "servers": {
    "local-llm": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "${workspaceFolder}", "local-llm-mcp"],
      "env": { "OLLAMA_HOST": "http://localhost:11434", "OLLAMA_MODEL": "qwen3:4b" }
    }
  }
}
```
Kullanım: Chat → **Agent** mode → araç listesinden `local-llm` işaretli olmalı → soru sor ya da `#ask_local_llm` ile zorla.

## Otomatik Kurulum (Bootstrap) Prensibi

Kullanıcı hiçbir şeyi elle kurmamalı. `uv run local-llm-mcp` (veya `setup.ps1`) çalıştığında sırayla:
1. Ollama kurulu değilse `winget` ile kur.
2. Ollama servisi kapalıysa `ollama serve`'ü detached başlat, `/api/tags` cevap verene kadar bekle.
3. `OLLAMA_MODEL` indirilmemişse `/api/pull` ile indir.
4. Modeli warm-up isteğiyle VRAM'e yükle.
5. `.vscode/mcp.json` yoksa üret.
6. MCP sunucusunu stdio'da başlat.

Tüm adımlar idempotent; çıktı sadece **stderr**'e. Bootstrap başarısız olsa bile sunucu ayağa kalkar, hata tool çağrısında döner.

## Git / Repo

- Uzak repo: **https://github.com/ksksertac/mcpserver** (`origin`, branch `main`)
- Her faz bitiminde commit + push. Commit mesajı Türkçe/İngilizce fark etmez, faz adıyla başlasın: `Faz 2: Ollama istemcisi`.

## Kurallar / Dikkat

- Python 3.14 çok yeni; bir paket uyumsuz çıkarsa `uv python install 3.12` ile 3.12'ye geç ve `pyproject`'te `requires-python = ">=3.12"` yaz.
- stdio sunucuda `print()` yasak → `logging` (stderr).
- Ollama'ya istek timeout'u yüksek tut (ilk yükleme 10–30 sn sürebilir): varsayılan 120 sn.
- qwen3 "thinking" modu çıktıya `<think>…</think>` ekleyebilir; `ollama_client` bu bloğu temizlemeli (veya `think: false` gönder).
- Her tool'un docstring'i LLM tarafından okunur — ne zaman kullanılacağını net yaz.
- Türkçe yanıt varsayılan; `style` ile değişir.
