# Local AI Agent + MCP Server

VS Code Chat'ten sorduğun soruyu **tamamen yerel** bir AI ajan cevaplar. Ajan; yerel LLM'e (Ollama) sorar, LLM "araç lazım" derse **MCP protokolü** ile kendi MCP sunucumuza gider, sonucu toparlayıp chat'e döner. Bulut yok, API anahtarı yok.

```
Sen ──► VS Code Chat ──HTTP──► AJAN (Python) ──► Ollama (qwen3:4b)  karar verir
                                   │                 │
                                   │◄── tool_call ───┘
                                   ├──MCP (stdio)──► MCP SERVER (Python)  tool'u çalıştırır
                                   │◄── sonuç ───────┘
                                   └──► Ollama ──► son cevap ──► VS Code
```

## Hızlı Başlangıç (Windows)

```powershell
git clone https://github.com/ksksertac/ai-agent-mcpserver.git
cd ai-agent-mcpserver
.\setup.ps1
```

`setup.ps1` sırayla: `uv` yoksa kurar → bağımlılıkları kurar → Ollama yoksa kurar → servisi başlatır → modeli indirir → VS Code ayarını yazar → ajanı başlatır. İkinci çalıştırmada hepsini atlar, 1–2 sn içinde ajan açılır.

Sonra VS Code'da: **Copilot Chat → model seçici → "Local Agent (Ollama + MCP)"** seç ve sor:

| Soru | Ne olur |
|---|---|
| `saat kaç?` | Ollama `sistem_bilgisi` tool'unu ister → ajan MCP'den alır → "Şu an saat 15:38" |
| `projede hangi md dosyaları var?` | `dosya_ara` → "CLAUDE.md, README.md, tasks.md" |
| `not al: yarın süt al` | `not_kaydet` → `.notes.json`'a yazar |
| `2+2 kaç?` | Tool çağırmaz, direkt "4" |

Cevabın altında `🔧 Kullanılan araçlar: ...` satırı hangi tool'ların çağrıldığını gösterir.

## Bileşenler

| Parça | Dosya | Görev |
|---|---|---|
| **AI Agent** | `src/local_llm/agent/` | OpenAI-uyumlu HTTP API (`:8000/v1`), Ollama ↔ MCP döngüsü, MCP client |
| **MCP Server** | `src/local_llm/mcp_server/` | Tool'lar: `sistem_bilgisi`, `dosya_ara`, `dosya_oku`, `not_kaydet`, `notlari_getir` |
| **Bootstrap** | `src/local_llm/bootstrap.py` | Ollama kur/başlat, model çek, warm-up, VS Code ayarı |
| **Ollama istemcisi** | `src/local_llm/ollama_client.py` | `/api/chat` (tool-calling), `/api/tags`, `/api/pull` |

## LLM tool'a gidip gitmeyeceğini nereden biliyor?

MCP sunucusundaki tool **docstring**'inden. Ajan her soruda bu açıklamaları Ollama'ya gönderir; Ollama soruyla karşılaştırıp karar verir:

```python
def not_kaydet(metin: str) -> str:
    """Kullanıcının verdiği metni kalıcı not olarak kaydeder.

    NE ZAMAN KULLAN: Kullanıcı "not al", "şunu kaydet", "hatırlat" dediğinde.
    NE ZAMAN KULLANMA: Kullanıcı sadece bilgi soruyorsa.
    """
```

Yeni bir yetenek eklemek = `mcp_server/tools/` altına böyle bir fonksiyon yazıp `server.py`'de kaydetmek. Ajan tarafında hiçbir değişiklik gerekmez.

## Model Seçimi

`scripts/tool_secim_testi.py` ile ölçüldü (10 alakalı + 10 alakasız soru, RTX 4060 8 GB):

| Model | Tool seçim isabeti | Hız |
|---|---|---|
| `qwen3:4b` (varsayılan) | **20/20** | ~11 sn/soru (model içten "düşünüyor") |
| `qwen2.5:3b` | 17/20 | **0.5 sn/soru** |

Hız istersen: `OLLAMA_MODEL=qwen2.5:3b uv run local-agent` (ya da `.env` dosyasına yaz).

## Komutlar

```powershell
uv run local-agent              # ajanı başlat (bootstrap otomatik)
uv run local-agent --check      # sadece kurulum kontrolü
uv run local-agent --no-bootstrap
uv run local-mcp                # MCP sunucusunu tek başına (stdio)
uv run pytest                   # tüm testler (Ollama gerekir)
uv run pytest -m "not integration"
uv run python scripts/tool_secim_testi.py qwen3:4b qwen2.5:3b
uv run ruff check src tests scripts
```

Ajan çalışırken: `http://127.0.0.1:8000/health` durum, `/v1/models` model listesi.

## Ayarlar (env veya `.env`)

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | |
| `OLLAMA_MODEL` | `qwen3:4b` | |
| `AGENT_PORT` | `8000` | |
| `MAX_TOOL_ROUNDS` | `5` | Bir soruda en fazla kaç tool turu |
| `MCP_SERVERS` | bizim sunucu | `isim=komut args;isim2=...` — başka MCP sunucuları da eklenebilir |
| `BOOTSTRAP` | `true` | `false` → kurulum adımlarını atla |

## VS Code'da görünmüyorsa

1. `.vscode/settings.json` içinde `github.copilot.chat.customOAIModels` girdisi var mı (bootstrap yazar).
2. Copilot eklentisi kurulu ve GitHub ile giriş yapılmış mı (ücretsiz plan yeterli).
3. Ajan çalışıyor mu: `curl http://127.0.0.1:8000/health`.
4. Yedek yol: Copilot → Manage Models → **Ollama** sağlayıcısı → endpoint `http://127.0.0.1:8000` (ajan Ollama API'sini de taklit eder).
5. Alternatif: `.vscode/mcp.json` ile MCP sunucusunu Copilot'un kendi modeline de bağlayabilirsin (Agent mode).
