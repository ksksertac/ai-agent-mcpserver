# Local LLM Agent + MCP Server

VS Code Chat'ten gelen soruyu **arkada çalışan kendi ajanımız** karşılar. Ajan yerel LLM'e (Ollama) sorar; LLM "tool lazım" derse ajan **kendisi** MCP sunucumuza gider, sonucu LLM'e verir, son cevabı chat'e döner. VS Code, MCP'yi hiç görmez; sadece bizim ajana bağlanır.

> Kaldığın yerden devam etmek için: önce [tasks.md](tasks.md) dosyasına bak, `[ ]` olan ilk taska başla. Biten taskı `[x]` yap.

## Ortam (tespit edildi — 2026-09-17)

| Bileşen | Durum |
|---|---|
| OS | Windows 11 Pro, PowerShell |
| Python | 3.14.3 sistemde; **uv venv 3.12.14 kullanıyor** (`requires-python >= 3.12`) |
| Paket yöneticisi | `uv` 0.12.15 — `uv sync`, `uv run …` |
| mcp SDK | **2.2.0** — `from mcp.server.mcpserver import MCPServer` (FastMCP yok), client: `ClientSession` + `stdio_client`, tool şeması `t.input_schema` |
| Ollama | 0.34.0 kurulu, `http://localhost:11434` |
| İndirilmiş modeller | `qwen3:4b` (tool-calling destekler, **varsayılan**), `qwen2.5:3b`, `qwen2.5vl:3b` |
| GPU | RTX 4060 Laptop 8 GB VRAM → 4B–8B q4 modeller rahat çalışır |
| VS Code | 1.138.0 |

## Mimari

```
                                    ┌──────────────── BİZİM UYGULAMA (arkada çalışır) ────────────────┐
                                    │                                                                  │
Sen ──► VS Code Chat ──HTTP────────►│  AJAN  (Python, FastAPI, OpenAI-uyumlu /v1/chat/completions)     │
        (model: "local-agent")      │    │                                                             │
                                    │    │ 1. MCP sunucusundan tool listesini al (docstring'ler)       │
                                    │    │ 2. soru + tool listesi → Ollama                             │
                                    │    ├──────HTTP /api/chat──────► Ollama (qwen3:4b)                │
                                    │    │◄─── cevap  veya  tool_call ─┘                               │
                                    │    │                                                             │
                                    │    │ 3. tool_call geldiyse AJAN KENDİSİ MCP'ye gider:            │
                                    │    ├──────stdio MCP client──────► MCP SERVER (Python, FastMCP)   │
                                    │    │◄─── tool sonucu ────────────┘   tools: sistem_bilgisi,      │
                                    │    │                                   dosya_ara, not_kaydet …   │
                                    │    │ 4. sonucu Ollama'ya ver → son cevap                         │
                                    │    │ 5. (tekrar tool_call gelirse 3'e dön, max N tur)            │
        ◄──── son cevap ────────────│    ▼                                                             │
                                    └──────────────────────────────────────────────────────────────────┘
```

### Akış — adım adım
1. VS Code Chat soruyu bizim ajana gönderir (OpenAI API formatında, sanki bir model gibi).
2. Ajan MCP sunucusuna bağlıdır; tool listesini (isim + docstring + parametre şeması) hazır tutar.
3. Ajan Ollama'ya **soru + tool listesi** gönderir.
4. Ollama ya düz cevap döner (alakasız soru) → ajan bunu chat'e verir, biter.
5. Ya da `tool_calls` döner → ajan MCP sunucusunda o tool'u çalıştırır, sonucu `role: tool` mesajı olarak Ollama'ya geri verir.
6. Ollama son cevabı üretir → ajan chat'e döner. (Birden fazla tur olabilir; `MAX_TOOL_ROUNDS` ile sınırlı.)

### LLM tool'a gidip gitmeyeceğini nereden biliyor?
**MCP sunucusundaki tool docstring'inden.** Ajan bu docstring'leri her soruda Ollama'ya gönderir; Ollama soruyla karşılaştırıp karar verir.

```python
@mcp.tool()
def siparis_getir(tarih: str) -> str:
    """Sipariş, fatura veya ciro sorulduğunda bunu kullan.
    Genel programlama/sohbet sorularında kullanma."""   # ← Ollama'nın gördüğü "kâğıt"
```
- "NE ZAMAN KULLAN / NE ZAMAN KULLANMA" yazmak 4B modelde isabeti ciddi artırır.
- Ajanın system prompt'u (`agent/prompts.py`) ek yönlendirme yapar ("emin değilsen tool'u kullan, uydurma").
- Docstring değişince MCP sunucusu yeniden başlar; ajan tool listesini tekrar çeker.

### Roller
| Kim | Ne yapar |
|---|---|
| VS Code Chat | Sadece arayüz. Soruyu ajana yollar, cevabı gösterir. |
| **Ajan** (bizim) | Beyin + eller. Ollama'ya sorar, kararı uygular, MCP'ye gider, döngüyü yönetir. |
| Ollama | Sadece beyin. Metin veya `tool_calls` üretir; ağa çıkamaz. |
| **MCP Server** (bizim) | Eller. Tool'ları çalıştırır, sonucu döner. Ollama'yı ÇAĞIRMAZ. |

## Proje Yapısı (mevcut)

```
mcpserver/
├── CLAUDE.md                  # bu dosya – proje hafızası
├── tasks.md                   # task listesi / ilerleme
├── pyproject.toml             # uv; entry point'ler: local-agent, local-mcp
├── setup.ps1                  # tek komut: uv → uv sync → bootstrap → ajanı başlat
├── .vscode/
│   ├── mcp.json               # (opsiyonel) MCP sunucusunu Copilot'un kendi modeline de tanıtır
│   └── settings.json          # github.copilot.chat.customOAIModels → http://127.0.0.1:8000/v1 (bootstrap yazar)
├── scripts/tool_secim_testi.py # model karşılaştırma: 10 alakalı + 10 alakasız soru
├── src/local_llm/
│   ├── __init__.py
│   ├── logging_setup.py       # stderr logger
│   ├── config.py              # OLLAMA_HOST, OLLAMA_MODEL, AGENT_PORT, MAX_TOOL_ROUNDS, MCP_SERVERS
│   ├── bootstrap.py           # ensure_ready(): Ollama kur/başlat, model çek, ısıt, MCP server başlat
│   ├── ollama_client.py       # httpx: /api/chat (tools ile), /api/tags, /api/pull
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── app.py             # FastAPI: POST /v1/chat/completions, GET /v1/models  (OpenAI uyumlu)
│   │   ├── loop.py            # ajan döngüsü: Ollama ↔ MCP tool_call turları
│   │   ├── mcp_client.py      # MCP sunucularına stdio ile bağlanır, tool listesi + call_tool
│   │   └── prompts.py         # ajan system prompt'u
│   └── mcp_server/
│       ├── __init__.py
│       ├── server.py          # FastMCP("local-tools"), main() → stdio
│       └── tools/             # gerçek yetenekler (Ollama'yı ÇAĞIRMAZ)
│           ├── system.py      # sistem_bilgisi
│           ├── files.py       # dosya_ara / dosya_oku
│           ├── notes.py       # not_kaydet / notlari_getir
│           └── mock.py        # sözde iş tool'ları (sipariş, fatura, doküman, git, docker, takvim)
└── tests/
    ├── test_ollama_client.py  # respx mock
    ├── test_mcp_server.py     # tool'lar doğrudan
    ├── test_agent_loop.py     # sahte Ollama + sahte MCP ile döngü
    └── test_bootstrap.py
```

## Teknoloji Kararları

- **Ajan API'si:** OpenAI-uyumlu `/v1/chat/completions` (FastAPI + uvicorn). VS Code Copilot Chat `customOAIModels` ile bağlanır; ileride Open WebUI, Continue vb. her istemci de bağlanabilir. Streaming (SSE) var ama cevap hazır olunca parça parça gönderilir (gerçek token akışı Faz 8).
- **Yedek plan:** Copilot custom-OAI çalışmazsa ajan Ollama-uyumlu `/api/chat` + `/api/tags` da sunar; VS Code'un Ollama sağlayıcısı ajanın portuna yönlendirilir.
- **MCP client:** resmi `mcp` SDK (`ClientSession` + `stdio_client`). Ajan MCP sunucusunu subprocess olarak başlatır. `MCP_SERVERS` config'i ile başka MCP sunucuları da eklenebilir.
- **MCP server:** `mcp` SDK `FastMCP`, transport stdio.
- **LLM:** Ollama `/api/chat`, `tools` parametresi ile native tool-calling. Varsayılan `qwen3:4b` (20/20 isabet, ~11 sn/soru); hızlı alternatif `qwen2.5:3b` (17/20, 0.5 sn).
- **think parametresi:** gönderilmiyor. qwen3:4b'de `think:false` düşünmeyi kapatmıyor, content'e karıştırıyor; verilmeyince Ollama ayrı `thinking` alanına koyar. `strip_think` yine de `</think>` kalıntısını temizler.
- **Test:** `pytest`, `pytest-asyncio`, `respx`. Gerçek Ollama gerektirenler `@pytest.mark.integration`.
- **Loglama:** MCP server stdio kullandığı için **stdout'a print yok** → `logging` stderr'e. Ajan normal loglayabilir.

## MCP Sunucunun Sunacakları

**Gerçek tools**
| Tool | Girdi | Docstring'de "ne zaman kullan" |
|---|---|---|
| `sistem_bilgisi` | – | Saat, tarih, OS, RAM/CPU/disk sorulduğunda |
| `dosya_ara` | `desen: str`, `klasor: str = "."` | Workspace'te dosya/isim arandığında |
| `dosya_oku` | `yol: str` | Belirli bir dosyanın içeriği istendiğinde |
| `not_kaydet` | `metin: str` | "Not al / hatırlat / kaydet" dendiğinde |
| `notlari_getir` | – | Kaydedilen notlar sorulduğunda |

**Sözde (mock) tools** — `tools/mock.py`, sabit cevap dönerler; gerçek entegrasyon yazılınca sadece gövde değişir
| Tool | Girdi | Ne zaman |
|---|---|---|
| `siparisleri_getir` | `tarih="bugün"` | sipariş, ciro, satış, kargoda |
| `musteri_faturasi` | `musteri` | "X'in faturası ödendi mi" |
| `dokuman_ara` | `kelime` | "sözleşmelerde X geçiyor mu" |
| `son_commit` | – | "son commit'te ne değişti" |
| `docker_listele` | – | "docker'da ne çalışıyor" |
| `takvim_bugun` | – | "bugün toplantım var mı" |

**Docstring yazma kuralı (ölçüldü):** "NE ZAMAN KULLAN: … geçiyorsa HER ZAMAN bu aracı çağır. Örnek: …" + "NE ZAMAN KULLANMA: … (diğer_tool)". Bu format + `temperature=0` ile qwen3:4b 11 tool'da %96 isabet.

> **Açık karar:** Mock tool'lar hangi gerçek sistemlere bağlanacak (DB/API/Docker/takvim)?

## Komutlar

```powershell
# tek komut kurulum + başlatma
.\setup.ps1

# geliştirme
uv sync
uv run local-agent            # ajan: http://localhost:8000  (bootstrap otomatik çalışır)
uv run local-mcp              # MCP sunucusunu tek başına çalıştır (stdio)
npx @modelcontextprotocol/inspector uv run local-mcp   # MCP tool'larını elle test

# ajanı VS Code'suz test
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"local-agent","messages":[{"role":"user","content":"saat kaç?"}]}'

# testler
uv run pytest
uv run pytest -m "not integration"

# Ollama (bootstrap otomatik yapar)
ollama serve / ollama list / ollama pull qwen3:4b
```

## VS Code Entegrasyonu

**Çalışan yol (VS Code 1.138):** Chat → model seçici → Manage/Language Models → **Add Models → Custom Endpoint → Chat Completions**. Kayıt `%APPDATA%/Code/User/chatLanguageModels.json` dosyasına düşer; bootstrap bunu otomatik yazar:
```json
[{"name":"local-agent","vendor":"customendpoint","apiType":"chat-completions",
  "models":[{"id":"local-agent","name":"Local Agent (Ollama + MCP)","url":"http://127.0.0.1:8000/v1",
             "toolCalling":false,"vision":false,"maxInputTokens":32000,"maxOutputTokens":4096}]}]
```
`customOAIModels` ayarı (aşağıda) bu sürümde listede görünmedi; geriye dönük uyumluluk için duruyor.


`.vscode/settings.json`:
```json
{
  "github.copilot.chat.customOAIModels": {
    "local-agent": {
      "name": "Local Agent (Ollama + MCP)",
      "url": "http://localhost:8000/v1",
      "toolCalling": false,
      "vision": false,
      "maxInputTokens": 32000,
      "maxOutputTokens": 4096
    }
  }
}
```
Kullanım: Chat → model seçici → **Local Agent** seç → soru sor. Tool kararı ve MCP çağrısı ajanın içinde olur; VS Code tarafında Agent mode gerekmez (`toolCalling: false`).

## Otomatik Kurulum (Bootstrap) Prensibi

Kullanıcı hiçbir şeyi elle kurmamalı. `uv run local-agent` (veya `setup.ps1`) çalıştığında sırayla:
1. Ollama kurulu değilse `winget` ile kur.
2. Ollama servisi kapalıysa `ollama serve`'ü detached başlat, `/api/tags` cevap verene kadar bekle.
3. `OLLAMA_MODEL` indirilmemişse `/api/pull` ile indir.
4. Modeli warm-up isteğiyle VRAM'e yükle.
5. MCP sunucusunu subprocess olarak başlat, tool listesini çek.
6. `.vscode/settings.json`'a `customOAIModels` yaz (eski yöntem) + `%APPDATA%/Code/User/chatLanguageModels.json`'a Custom Endpoint girdisi yaz (VS Code 1.138'de çalışan yöntem).
7. Ajan HTTP sunucusunu :8000'de aç, "VS Code'da Local Agent'ı seçin" mesajı ver.

Tüm adımlar idempotent. Bootstrap başarısız olsa bile ajan ayağa kalkar; hata chat cevabında açıklanır.

## Git / Repo

- Uzak repo: **https://github.com/ksksertac/ai-agent-mcpserver** (`origin`, branch `main`)
- Her faz bitiminde commit + push. Commit mesajı faz adıyla başlasın: `Faz 2: Ollama istemcisi`.

## Kurallar / Dikkat

- uv otomatik Python 3.12 kullanıyor; sistemdeki 3.14'e bağımlı değiliz.
- Ajan çalışırken `uv sync` / `uv run` `local-agent.exe`'yi kilitler → önce ajanı durdur (port 8000'i tutan PID).
- Uzun dosyaları bash heredoc ile yazma (EOF hatası); Write tool'u kullan.
- Windows terminalinde Türkçe çıktı için `PYTHONIOENCODING=utf-8`.
- MCP server'da `print()` yasak → `logging` (stderr).
- Ollama timeout yüksek (ilk yükleme 10–30 sn): varsayılan 120 sn.
- qwen3 düşünce üretir; `think` gönderilmez, Ollama ayrı alana koyar, `strip_think` kalıntıyı temizler.
- Ajan döngüsü `MAX_TOOL_ROUNDS` (varsayılan 5) ile sınırlı; sonsuz tool döngüsü engellenir.
- MCP tool'ları Ollama'yı çağırmaz. Beyin = Ollama, eller = ajan + MCP server.
- Copilot custom-OAI sağlayıcısı için Copilot eklentisi + GitHub girişi gerekir (ücretsiz plan yeterli).
