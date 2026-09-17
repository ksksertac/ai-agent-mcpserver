"""dosya_ara ve dosya_oku tool'ları. Sadece proje kökü altında çalışır."""

from pathlib import Path

from local_llm.config import PROJECT_ROOT

MAX_RESULTS = 50
MAX_READ_BYTES = 20_000
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}


def _safe_path(rel: str) -> Path:
    p = (PROJECT_ROOT / rel).resolve()
    if PROJECT_ROOT not in p.parents and p != PROJECT_ROOT:
        raise ValueError(f"Proje kökü dışına erişim yok: {rel}")
    return p


def dosya_ara(desen: str, klasor: str = ".") -> str:
    """Proje klasöründeki dosyaları LİSTELER (glob deseni: "*.py", "test_*", "*.md").
    Proje dosyalarının listesi SADECE bu araçtan alınabilir.

    NE ZAMAN KULLAN: Soruda "hangi dosyalar", "dosyaları listele", "py/md dosyaları",
    "X dosyası nerede", "dosyayı bul" geçiyorsa HER ZAMAN bu aracı çağır.
    Örnek: "projede hangi py dosyaları var?", "README nerede?".
    NE ZAMAN KULLANMA: Belirli bir dosyanın içeriği istendiğinde (dosya_oku).
    """
    root = _safe_path(klasor)
    if not root.is_dir():
        return f"Klasör bulunamadı: {klasor}"
    if "*" not in desen and "?" not in desen:
        desen = f"*{desen}*"
    hits: list[str] = []
    for p in root.rglob(desen):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        hits.append(str(p.relative_to(PROJECT_ROOT)))
        if len(hits) >= MAX_RESULTS:
            hits.append(f"... (ilk {MAX_RESULTS} sonuç gösterildi)")
            break
    return "\n".join(hits) if hits else f"'{desen}' desenine uyan dosya yok."


def dosya_oku(yol: str) -> str:
    """Adı verilen bir dosyanın İÇERİĞİNİ okur ve döner (ilk 20 KB).

    NE ZAMAN KULLAN: Kullanıcı dosya adını söyleyip "içinde ne yazıyor", "içeriği ne", "oku",
    "ne var" dediğinde. Örnek: "pyproject.toml içinde ne yazıyor?", "README'yi oku".
    Dosya adı sorudaysa dosya_ara DEĞİL bunu kullan.
    NE ZAMAN KULLANMA: Dosya adı bilinmiyor, sadece hangi dosyaların olduğu soruluyorsa (dosya_ara).
    """
    p = _safe_path(yol)
    if not p.is_file():
        return f"Dosya bulunamadı: {yol}"
    data = p.read_bytes()[:MAX_READ_BYTES]
    text = data.decode("utf-8", errors="replace")
    if p.stat().st_size > MAX_READ_BYTES:
        text += f"\n... (dosya {p.stat().st_size} byte, ilk {MAX_READ_BYTES} byte gösterildi)"
    return text
