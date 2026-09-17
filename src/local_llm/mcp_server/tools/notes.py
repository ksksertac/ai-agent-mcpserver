"""not_kaydet ve notlari_getir tool'ları. Notlar JSON dosyasında tutulur."""

import json
from datetime import datetime

from local_llm.config import settings


def _load() -> list[dict]:
    if settings.notes_file.exists():
        return json.loads(settings.notes_file.read_text(encoding="utf-8"))
    return []


def _save(notes: list[dict]) -> None:
    settings.notes_file.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def not_kaydet(metin: str) -> str:
    """Kullanıcının verdiği metni kalıcı not olarak kaydeder.

    NE ZAMAN KULLAN: Kullanıcı "not al", "şunu kaydet", "hatırlat", "unutma" dediğinde.
    NE ZAMAN KULLANMA: Kullanıcı sadece bilgi soruyorsa; kaydetme isteği yoksa.
    """
    notes = _load()
    notes.append(
        {
            "id": len(notes) + 1,
            "zaman": datetime.now().isoformat(timespec="seconds"),
            "metin": metin,
        }
    )
    _save(notes)
    return f"Not #{len(notes)} kaydedildi: {metin}"


def notlari_getir() -> str:
    """Daha önce kaydedilmiş tüm notları listeler.

    NE ZAMAN KULLAN: Kullanıcı "notlarım neler", "ne kaydetmiştim", "notları göster" dediğinde.
    NE ZAMAN KULLANMA: Yeni not eklenmek isteniyorsa (onun için not_kaydet).
    """
    notes = _load()
    if not notes:
        return "Kayıtlı not yok."
    return "\n".join(f"#{n['id']} [{n['zaman']}] {n['metin']}" for n in notes)
