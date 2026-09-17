"""SÖZDE (mock) tool'lar — sabit cevap dönerler.

Amaç: gerçek entegrasyon (DB, API, Docker...) yazılmadan önce akışı ve tool seçimini denemek.
Gerçeğe geçerken sadece fonksiyon gövdesi değişir; docstring ve imza aynı kalabilir.
"""

from __future__ import annotations

_SIPARISLER = [
    {"no": "S-1041", "musteri": "Ayşe Yılmaz", "tutar": 1250.00, "durum": "kargoda"},
    {"no": "S-1042", "musteri": "Mehmet Kaya", "tutar": 480.50, "durum": "hazırlanıyor"},
    {"no": "S-1043", "musteri": "Deniz Ltd.", "tutar": 9800.00, "durum": "teslim edildi"},
]

_FATURALAR = {
    "ayşe yılmaz": {"no": "F-2026-0917", "tarih": "2026-09-15", "tutar": 1250.00, "odendi": False},
    "mehmet kaya": {"no": "F-2026-0902", "tarih": "2026-09-02", "tutar": 480.50, "odendi": True},
    "deniz ltd.": {"no": "F-2026-0888", "tarih": "2026-08-28", "tutar": 9800.00, "odendi": True},
}

_DOKUMANLAR = [
    (
        "sozlesmeler/deniz-ltd-2026.pdf",
        "Madde 12: Taraflardan biri 30 gün önceden yazılı bildirimle fesih edebilir.",
    ),
    ("sozlesmeler/ayse-yilmaz-bayilik.docx", "Fesih halinde stoklar 15 gün içinde iade edilir."),
    ("ik/personel-yonetmeligi.pdf", "İş akdinin feshi İş Kanunu 17. maddeye tabidir."),
]

_CONTAINERS = [
    {"ad": "web", "imaj": "nginx:1.27", "durum": "Up 3 days", "port": "80→8080"},
    {"ad": "api", "imaj": "myapp/api:2.4.1", "durum": "Up 3 days", "port": "5000→5000"},
    {"ad": "db", "imaj": "postgres:16", "durum": "Up 3 days", "port": "5432→5432"},
    {"ad": "worker", "imaj": "myapp/worker:2.4.1", "durum": "Exited (1) 2 hours ago", "port": "-"},
]

_TAKVIM = [
    ("09:30", "10:00", "Günlük stand-up"),
    ("11:00", "12:00", "Deniz Ltd. sözleşme görüşmesi"),
    ("14:00", "15:30", "Sprint planlama"),
    ("17:00", "17:30", "1:1 – Mehmet"),
]


def siparisleri_getir(tarih: str = "bugün") -> str:
    """Sipariş sistemindeki siparişleri listeler: sipariş no, müşteri, tutar, durum ve toplam ciro.
    Sipariş verisi SADECE bu araçtan alınabilir; tarih vermek zorunlu değildir (varsayılan: bugün).

    NE ZAMAN KULLAN: Soruda "sipariş", "siparişler", "ciro", "satış", "kargoda", "ne kadar tuttu",
    "kaç sipariş" geçiyorsa HER ZAMAN bu aracı çağır. Örnek: "bugünkü siparişler ne kadar tuttu?",
    "kargoda kaç sipariş var?", "dünkü satışlar?".
    NE ZAMAN KULLANMA: Belirli bir müşterinin faturası sorulduğunda (musteri_faturasi).
    [MOCK: sabit veri döner]
    """
    satirlar = [
        f"- {s['no']} | {s['musteri']} | {s['tutar']:.2f} TL | {s['durum']}" for s in _SIPARISLER
    ]
    toplam = sum(s["tutar"] for s in _SIPARISLER)
    return (
        f"{tarih} için {len(_SIPARISLER)} sipariş:\n"
        + "\n".join(satirlar)
        + f"\nToplam ciro: {toplam:.2f} TL"
    )


def musteri_faturasi(musteri: str) -> str:
    """Bir müşterinin son faturasını getirir (fatura no, tarih, tutar, ödendi mi).

    NE ZAMAN KULLAN: Kullanıcı bir müşteri adı verip "faturası", "borcu var mı", "ödedi mi",
    "son fatura" dediğinde.
    NE ZAMAN KULLANMA: Müşteri adı yoksa; sipariş listesi istendiğinde (siparisleri_getir).
    [MOCK: sabit veri döner]
    """
    f = _FATURALAR.get(musteri.strip().lower())
    if not f:
        bilinen = ", ".join(k.title() for k in _FATURALAR)
        return f"'{musteri}' için fatura bulunamadı. Bilinen müşteriler: {bilinen}"
    durum = "ödendi" if f["odendi"] else "ÖDENMEDİ"
    return f"{musteri.title()} – son fatura {f['no']} ({f['tarih']}): {f['tutar']:.2f} TL, {durum}."


def dokuman_ara(kelime: str) -> str:
    """Şirket dokümanlarında (sözleşme, yönetmelik, PDF/Word) anahtar kelime arar.

    NE ZAMAN KULLAN: Kullanıcı "sözleşmelerde X geçiyor mu", "dokümanlarda ara",
    "hangi belgede ... yazıyor" dediğinde.
    NE ZAMAN KULLANMA: Proje kod dosyaları için (dosya_ara/dosya_oku), genel sorularda.
    [MOCK: sabit veri döner]
    """
    k = kelime.lower()
    hits = [
        f'- {yol}: "{parca}"'
        for yol, parca in _DOKUMANLAR
        if k in parca.lower() or k in yol.lower()
    ]
    if not hits:
        return f"'{kelime}' hiçbir dokümanda geçmiyor. (Taranan: {len(_DOKUMANLAR)} belge)"
    return f"'{kelime}' {len(hits)} belgede geçiyor:\n" + "\n".join(hits)


def son_commit() -> str:
    """Projenin git geçmişindeki son commit'i gösterir (hash, yazar, mesaj, değişen dosyalar).

    NE ZAMAN KULLAN: Kullanıcı "son commit ne", "en son ne değişti", "kim ne push etti" dediğinde.
    NE ZAMAN KULLANMA: Dosya içeriği istendiğinde (dosya_oku), genel git sorularında.
    [MOCK: sabit veri döner]
    """
    return (
        "Son commit: a1b2c3d (2 saat önce) – Sertaç\n"
        "Mesaj: Faz 5-7: bootstrap + setup.ps1, VS Code entegrasyonu\n"
        "Değişen: src/local_llm/bootstrap.py (+120), setup.ps1 (+48), README.md (+95)"
    )


def docker_listele() -> str:
    """Çalışan/duran Docker container'larını listeler (ad, imaj, durum, port).

    NE ZAMAN KULLAN: Kullanıcı "container'lar", "docker'da ne çalışıyor", "hangi servis ayakta",
    "docker ps" dediğinde.
    NE ZAMAN KULLANMA: Bilgisayarın RAM/CPU'su sorulduğunda (sistem_bilgisi).
    [MOCK: sabit veri döner]
    """
    rows = [f"- {c['ad']:<7} {c['imaj']:<20} {c['durum']:<24} {c['port']}" for c in _CONTAINERS]
    down = [c["ad"] for c in _CONTAINERS if not c["durum"].startswith("Up")]
    uyari = f"\nUYARI: duran container: {', '.join(down)}" if down else ""
    return f"{len(_CONTAINERS)} container:\n" + "\n".join(rows) + uyari


def takvim_bugun() -> str:
    """Bugünkü takvim etkinliklerini/toplantıları listeler.

    NE ZAMAN KULLAN: Kullanıcı "bugün toplantım var mı", "takvimim", "programım ne",
    "sıradaki toplantı" dediğinde.
    NE ZAMAN KULLANMA: Sadece saat/tarih sorulduğunda (sistem_bilgisi), not almak istendiğinde.
    [MOCK: sabit veri döner]
    """
    rows = [f"- {b}–{e}  {ad}" for b, e, ad in _TAKVIM]
    return f"Bugün {len(_TAKVIM)} etkinlik:\n" + "\n".join(rows)
