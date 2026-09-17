# Tasks

Durum işaretleri: `[ ]` yapılmadı · `[~]` devam ediyor · `[x]` bitti
Her faz sonunda commit at ve `origin main`'e push et (repo: https://github.com/ksksertac/ai-agent-mcpserver).

İki parça yazıyoruz: **AI Agent** (beyin+eller: Ollama'ya sorar, MCP'ye gider) ve **MCP Server** (sadece tool'lar). Detay: [CLAUDE.md](CLAUDE.md).

## Faz 0 — Planlama & Repo
- [x] Ortam tespiti (Python 3.14, uv, Ollama 0.34, qwen3:4b, RTX 4060 8GB, VS Code 1.138)
- [x] Mimari ve plan → `CLAUDE.md`
- [x] Task listesi → `tasks.md`
- [x] `git init`, `.gitignore`, ilk commit, `origin` = github.com/ksksertac/ai-agent-mcpserver, push
- [x] Mimari kararı: bizim ajan MCP client olacak, VS Code sadece arayüz (2026-09-17)

## Faz 1 — Proje İskeleti
- [x] `uv init` ile `pyproject.toml` (`name = local-llm`, `requires-python >= 3.12`)
- [x] Bağımlılıklar: `mcp[cli]`, `httpx`, `fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`
- [x] Dev bağımlılıklar: `pytest`, `pytest-asyncio`, `respx`, `ruff`
- [x] Paket yapısı: `src/local_llm/{config.py, bootstrap.py, ollama_client.py, agent/, mcp_server/}`
- [x] Entry point'ler: `local-agent = local_llm.agent.app:main`, `local-mcp = local_llm.mcp_server.server:main`
- [x] `config.py`: `OLLAMA_HOST`, `OLLAMA_MODEL=qwen3:4b`, `OLLAMA_TIMEOUT=120`, `AGENT_PORT=8000`, `MAX_TOOL_ROUNDS=5`, `MCP_SERVERS` (komut listesi)
- [x] Python 3.14 ile `uv sync` sorunsuz mu; değilse 3.12'ye geç → uv otomatik 3.12.14 seçti, mcp 2.2.0 (FastMCP → MCPServer)
- [x] `logging` ayarı: MCP server stderr'e, ajan normal

## Faz 2 — MCP Server (eller)
- [x] `mcp_server/server.py`: `FastMCP("local-tools")`, `main()` → `mcp.run(transport="stdio")`
- [x] Tool `sistem_bilgisi()` — saat, tarih, OS, RAM/CPU/disk
- [x] Tool `dosya_ara(desen, klasor=".")` — workspace'te glob arama
- [x] Tool `dosya_oku(yol)` — dosya içeriği (boyut sınırı ile)
- [x] Tool `not_kaydet(metin)` / `notlari_getir()` — JSON dosyasına basit not
- [x] Her tool docstring'i "NE ZAMAN KULLAN / NE ZAMAN KULLANMA" formatında (Ollama kararını buradan veriyor)
- [x] `tests/test_mcp_server.py` — tool fonksiyonları doğrudan test
- [x] MCP protokolü doğrulandı: test içinde stdio_client ile gerçek subprocess (Inspector yerine)
- [ ] **AÇIK KARAR:** tool'ların asıl konusu belirlenince demo tool'lar değişecek

## Faz 3 — Ollama İstemcisi
- [ ] `ollama_client.py`: `async chat(messages, tools=None, model=None) -> OllamaResponse` (`POST /api/chat`, `stream: false`, `think: false`)
- [ ] Cevaptaki `message.tool_calls` listesini parse et (name + arguments)
- [ ] `async list_models()` (`GET /api/tags`), `async pull(model)` (`POST /api/pull`, stream ile ilerleme)
- [ ] `<think>…</think>` temizleme
- [ ] Hata yönetimi: Ollama kapalı / model yok → anlaşılır mesaj
- [ ] `tests/test_ollama_client.py` — respx mock (düz cevap + tool_call cevabı)
- [ ] Gerçek Ollama ile tool-calling smoke test (`@pytest.mark.integration`): "saat kaç?" → `tool_calls` dönüyor mu

## Faz 4 — AI Agent (beyin + eller)
- [ ] `agent/mcp_client.py`: `MCP_SERVERS`'daki her sunucuyu `stdio_client` ile başlat, `ClientSession` aç, `list_tools()` → Ollama tool formatına çevir, `call_tool(name, args)`
- [ ] `agent/prompts.py`: ajan system prompt'u (Türkçe, "emin değilsen tool kullan, uydurma", cevap formatı)
- [ ] `agent/loop.py`: `run(messages) -> str`
  - Ollama'ya `messages + tools` gönder
  - `tool_calls` yoksa → cevabı döndür
  - varsa → her tool'u MCP'de çalıştır, `role: tool` mesajı ekle, tekrar Ollama'ya sor
  - `MAX_TOOL_ROUNDS` aşılırsa dur, elindeki en iyi cevabı ver
  - her turu logla (hangi tool, hangi argüman, kaç ms)
- [ ] `agent/app.py`: FastAPI
  - `POST /v1/chat/completions` (OpenAI uyumlu; `stream=false`)
  - `GET /v1/models` → `local-agent`
  - startup'ta bootstrap + MCP bağlantısı, shutdown'da MCP kapat
  - `main()` → uvicorn `AGENT_PORT`
- [ ] `tests/test_agent_loop.py` — sahte Ollama (respx) + sahte MCP client ile: düz cevap, tek tool turu, çoklu tur, MAX_TOOL_ROUNDS
- [ ] `curl` ile uçtan uca test: "saat kaç?" → `sistem_bilgisi` çağrılıp cevap dönüyor mu; "Python'da liste nasıl sıralanır?" → tool çağrılmadan cevap
- [ ] Tool seçim testi: 10 alakalı + 10 alakasız soru → isabet oranı; düşükse docstring/prompt düzelt, hâlâ düşükse `qwen3:8b`

## Faz 5 — Otomatik Kurulum & Başlatma (Bootstrap)
Hedef: `.\setup.ps1` veya `uv run local-agent` ile **hiçbir şey elle kurmadan** her şey hazırlanıp açılsın.
- [ ] `bootstrap.py`: `ensure_ready()` — ajan startup'ında çağrılır
- [ ] Ollama kurulu mu (`ollama --version`); değilse `winget install Ollama.Ollama`, kullanıcıya bilgi ver
- [ ] Ollama servisi ayakta mı (`GET /api/tags`); değilse `ollama serve` detached başlat, hazır olana kadar bekle (max 30 sn)
- [ ] Model indirilmiş mi; değilse `/api/pull` ile indir, ilerlemeyi logla
- [ ] Warm-up: boş `/api/chat` ile modeli VRAM'e yükle
- [ ] MCP sunucusunu subprocess olarak başlat (mcp_client zaten yapıyor, hata durumunda anlaşılır mesaj)
- [ ] `.vscode/settings.json`'a `customOAIModels` girdisini yaz (varsa dokunma)
- [ ] `setup.ps1`: `uv` yoksa `winget install astral-sh.uv`, `uv sync`, `uv run local-agent`, sonunda "VS Code'da Local Agent'ı seçin" mesajı
- [ ] `--no-bootstrap` / `--check` CLI bayrakları
- [ ] İdempotent: ikinci çalıştırma 1–2 sn içinde geçsin
- [ ] Bootstrap hatası ajanı düşürmesin; chat cevabında açıklansın
- [ ] `tests/test_bootstrap.py` — subprocess/httpx mock

## Faz 6 — VS Code Entegrasyonu
- [ ] `.vscode/settings.json`: `github.copilot.chat.customOAIModels` → `http://localhost:8000/v1`, `toolCalling: false`
- [ ] Copilot Chat → model seçici → **Local Agent** görünüyor mu
- [ ] Chat'ten "saat kaç?" → ajan logunda `sistem_bilgisi` çağrısı, chat'te doğru cevap
- [ ] Chat'ten alakasız soru → tool çağrılmadan cevap
- [ ] Custom-OAI çalışmazsa **yedek plan**: ajana Ollama-uyumlu `/api/chat` + `/api/tags` ekle, VS Code Ollama sağlayıcısını `http://localhost:8000`'e yönlendir
- [ ] (Opsiyonel) `.vscode/mcp.json` ile MCP sunucusunu VS Code'a da tanıt — Copilot bulut modeliyle karşılaştırma için

## Faz 7 — İyileştirme & Yayın
- [ ] Streaming (SSE) cevap — `stream=true` desteği, VS Code'da kelime kelime akış
- [ ] Konuşma geçmişi: VS Code zaten `messages` ile gönderiyor; uzun geçmişte kırpma
- [ ] Birden fazla MCP sunucusu (`MCP_SERVERS` listesi, ör. dosya sistemi + GitHub)
- [ ] Tool sonuçlarını chat'te göster ("🔧 sistem_bilgisi çağrıldı")
- [ ] README.md (kurulum, kullanım, mimari şema, ekran görüntüsü)
- [ ] `ruff` lint + format, `uv run pytest` yeşil
- [ ] Final commit + push

## Notlar / Kararlar
- 2026-09-17: Model `qwen3:4b` (tool-calling + Türkçe + VRAM). İsabet düşükse `qwen3:8b`.
- 2026-09-17: Uzak repo: https://github.com/ksksertac/ai-agent-mcpserver
- 2026-09-17: Tek komutla otomatik kurulum (bootstrap) istendi → Faz 5
- 2026-09-17: **Mimari:** bizim ajan = MCP client. Akış: VS Code → Ajan → Ollama (karar) → Ajan → MCP Server (tool) → Ajan → Ollama (son cevap) → VS Code. LLM sadece karar verir, MCP'ye giden ajandır (LLM'in ağ erişimi yok).
- 2026-09-17: Ajan OpenAI-uyumlu API sunar (`/v1/chat/completions`); VS Code `customOAIModels` ile bağlanır. Yedek: Ollama-uyumlu API.
- 2026-09-17: MCP tool'ları Ollama'yı çağırmaz (döngü olur). Tool'lar gerçek yetenek.
- **AÇIK KARAR:** MCP tool'larının asıl konusu ne olacak? Şimdilik demo: sistem_bilgisi, dosya_ara, dosya_oku, not_kaydet.
