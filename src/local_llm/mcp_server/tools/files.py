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
    """Proje klasöründe dosya adına göre arama yapar (glob deseni, ör. "*.py", "test_*", "*.md").

    NE ZAMAN KULLAN: Kullanıcı "hangi dosyalar var", "py dosyalarını listele", "config dosyası nerede",
    "X isimli dosyayı bul" gibi dosya/klasör listesi veya konumu sorduğunda.
    NE ZAMAN KULLANMA: Dosya içeriği istendiğinde (onun için dosya_oku), genel sorularda.
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
    """Proje klasöründeki bir dosyanın içeriğini okur (ilk 20 KB).

    NE ZAMAN KULLAN: Kullanıcı belirli bir dosyanın içeriğini, ne yazdığını, kaç satır olduğunu
    sorduğunda; "README'yi oku", "config.py'de ne var" gibi.
    NE ZAMAN KULLANMA: Dosya adı bilinmiyorsa (önce dosya_ara), genel sorularda.
    """
    p = _safe_path(yol)
    if not p.is_file():
        return f"Dosya bulunamadı: {yol}"
    data = p.read_bytes()[:MAX_READ_BYTES]
    text = data.decode("utf-8", errors="replace")
    if p.stat().st_size > MAX_READ_BYTES:
        text += f"\n... (dosya {p.stat().st_size} byte, ilk {MAX_READ_BYTES} byte gösterildi)"
    return text
