# Tasks

Durum işaretleri: `[ ]` yapılmadı · `[~]` devam ediyor · `[x]` bitti
Her faz sonunda commit at ve `origin main`'e push et (repo: https://github.com/ksksertac/mcpserver).

## Faz 0 — Planlama & Repo
- [x] Ortam tespiti (Python 3.14, uv, Ollama 0.34, qwen3:4b, RTX 4060 8GB, VS Code 1.138)
- [x] Mimari ve plan → `CLAUDE.md`
- [x] Task listesi → `tasks.md`
- [x] `git init`, `.gitignore`, ilk commit, `origin` = github.com/ksksertac/mcpserver, push

## Faz 1 — Proje İskeleti
- [ ] `uv init` ile `pyproject.toml` oluştur (`name = local-llm-mcp`, `requires-python >= 3.12`)
- [ ] Bağımlılıklar: `mcp[cli]`, `httpx`, `pydantic`, `pydantic-settings`
- [ ] Dev bağımlılıklar: `pytest`, `pytest-asyncio`, `respx`, `ruff`
- [ ] `src/local_llm_mcp/` paket yapısını oluştur (`__init__.py`, `server.py`, `config.py`, `ollama_client.py`, `prompts.py`, `tools/`)
- [ ] `[project.scripts] local-llm-mcp = "local_llm_mcp.server:main"` entry point
- [ ] Python 3.14 ile `uv sync` sorunsuz mu kontrol et; değilse 3.12'ye geç
- [ ] `logging` stderr'e ayarlanmış olsun (stdout'a print yok)

## Faz 1.5 — Otomatik Kurulum & Başlatma (Bootstrap)
Hedef: kullanıcı tek komutla (`uv run local-llm-mcp` / `setup.ps1`) çalıştırınca **hiçbir şey elle kurmadan** her şey hazırlanıp açılsın.
- [ ] `src/local_llm_mcp/bootstrap.py`: sunucu `main()` başlamadan önce çağrılan `ensure_ready()` fonksiyonu
- [ ] Ollama kurulu mu kontrol et (`ollama --version`); değilse `winget install Ollama.Ollama` çalıştır (Windows), kullanıcıya stderr'de bilgi ver
- [ ] Ollama servisi ayakta mı (`GET /api/tags`); değilse `ollama serve`'ü arka planda başlat (`subprocess.Popen`, detached) ve hazır olana kadar bekle (max 30 sn)
- [ ] Model indirilmiş mi (`/api/tags` içinde `OLLAMA_MODEL`); değilse `POST /api/pull` ile indir, ilerlemeyi stderr'e yaz
- [ ] Modeli ısıt (warm-up): boş bir `/api/chat` isteği ile VRAM'e yükle, ilk soru gecikmesin
- [ ] `.vscode/mcp.json` yoksa otomatik oluştur (workspace kökü tespiti)
- [ ] `setup.ps1` (repo kökü): `uv` yoksa kur (`winget install astral-sh.uv`), `uv sync`, ardından `uv run local-llm-mcp --check` ile bootstrap'ı tetikle, sonunda "VS Code'u açıp Chat → Agent moda geçin" mesajı
- [ ] `--check` / `--no-bootstrap` CLI bayrakları (bootstrap'ı sadece çalıştır / atla)
- [ ] Bootstrap adımları idempotent olsun: ikinci çalıştırmada hiçbir şeyi yeniden kurmasın, 1–2 sn içinde geçsin
- [ ] Bootstrap hataları sunucuyu düşürmesin; anlaşılır mesajla devam etsin (Ollama yoksa tool çağrısında hata dönsün)
- [ ] `tests/test_bootstrap.py` — subprocess/httpx mock ile

## Faz 2 — Ollama İstemcisi
- [ ] `config.py`: `OLLAMA_HOST` (default `http://localhost:11434`), `OLLAMA_MODEL` (default `qwen3:4b`), `OLLAMA_TIMEOUT` (default 120), `DEFAULT_STYLE`
- [ ] `ollama_client.py`: `async chat(messages, model=None, options=None) -> str` (`POST /api/chat`, `stream: false`, `think: false`)
- [ ] `ollama_client.py`: `async list_models() -> list[dict]` (`GET /api/tags`)
- [ ] `<think>…</think>` bloklarını temizleyen yardımcı
- [ ] Hata yönetimi: Ollama kapalıysa anlaşılır mesaj ("`ollama serve` çalıştırın"), model yoksa "`ollama pull <model>`"
- [ ] `tests/test_ollama_client.py` — respx ile mock'lu testler
- [ ] Gerçek Ollama ile smoke test (`@pytest.mark.integration`)

## Faz 3 — MCP Sunucusu (tools / prompts / resources)
- [ ] `server.py`: `FastMCP("local-llm")` oluştur, `main()` → `mcp.run(transport="stdio")`
- [ ] `prompts.py`: style şablonları (`kısa`, `detaylı`, `json`, `markdown`) + Türkçe varsayılan system prompt
- [ ] Tool `ask_local_llm(question, style="markdown", system_prompt=None, model=None)`
- [ ] Tool `summarize_text(text, max_sentences=3)`
- [ ] Tool `explain_code(code, language=None)`
- [ ] Tool `review_code(code)` → madde madde bulgular
- [ ] Tool `list_models()`
- [ ] Prompt `turkish_assistant`, Prompt `code_reviewer`
- [ ] Resource `ollama://models`, Resource `config://current`
- [ ] Tool docstring'leri LLM'in ne zaman çağıracağını net anlatsın
- [ ] `tests/test_tools.py` — tool'lar mock client ile test
- [ ] MCP Inspector ile elle doğrula: `npx @modelcontextprotocol/inspector uv run local-llm-mcp`

## Faz 4 — VS Code Entegrasyonu
- [ ] `.vscode/mcp.json` oluştur (stdio, `uv run --directory ${workspaceFolder} local-llm-mcp`)
- [ ] VS Code'da sunucuyu başlat (Command Palette → "MCP: List Servers" → Start), log'ları kontrol et
- [ ] Chat → Agent mode → `#ask_local_llm` ile soru sor, yerel LLM'den cevap geldiğini doğrula
- [ ] Otomatik tool seçimini test et (tool ismi vermeden soru sor)
- [ ] `/turkish_assistant` prompt'unun Chat'te göründüğünü doğrula
- [ ] Cevap formatının (style) istendiği gibi olduğunu doğrula; gerekirse `prompts.py` ayarla

## Faz 5 — Tamamen Yerel Döngü (opsiyonel)
- [ ] VS Code Copilot Chat → Manage Models → Ollama sağlayıcısını ekle, `qwen3:4b` seç
- [ ] Yerel model + MCP tool'larının birlikte çalıştığını test et (Ollama model ↔ MCP ↔ Ollama)
- [ ] Ollama tool-calling kalitesi yetersizse `qwen3:8b` veya `llama3.1:8b` dene (8 GB VRAM sınırı)

## Faz 6 — İyileştirme & Yayın
- [ ] Streaming cevap (MCP progress notification ile) — uzun cevaplarda UX
- [ ] `streamable-http` transport seçeneği (`--transport http`), uzaktan kullanım
- [ ] Konuşma geçmişi / session bağlamı (kısa süreli bellek)
- [ ] README.md (kurulum, kullanım, ekran görüntüsü)
- [ ] `ruff` lint + format, `uv run pytest` yeşil
- [ ] Final commit + push

## Notlar / Kararlar
- 2026-09-17: Model olarak `qwen3:4b` seçildi (tool-calling + Türkçe + VRAM uyumu).
- 2026-09-17: Transport stdio; HTTP sonraya bırakıldı.
- 2026-09-17: Uzak repo: https://github.com/ksksertac/mcpserver
- 2026-09-17: Tek komutla otomatik kurulum (bootstrap) istendi → Faz 1.5
