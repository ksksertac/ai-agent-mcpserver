"""sistem_bilgisi tool'u."""

import platform
import shutil
from datetime import datetime

import psutil


def sistem_bilgisi() -> str:
    """Bu bilgisayarın anlık durumunu verir: saat, tarih, işletim sistemi, CPU, RAM ve disk kullanımı.

    NE ZAMAN KULLAN: Kullanıcı "saat kaç", "bugün günlerden ne", "tarih ne", "RAM ne kadar dolu",
    "disk ne kadar boş", "CPU yüzde kaç", "hangi işletim sistemi" gibi bu makineyle ilgili
    anlık bilgi sorduğunda.
    NE ZAMAN KULLANMA: Genel bilgi, programlama, matematik veya sohbet sorularında.
    """
    now = datetime.now()
    vm = psutil.virtual_memory()
    du = shutil.disk_usage("/")
    gb = 1024**3
    return "\n".join(
        [
            f"Tarih: {now:%Y-%m-%d} ({now:%A})",
            f"Saat: {now:%H:%M:%S}",
            f"İşletim sistemi: {platform.system()} {platform.release()}",
            f"Makine adı: {platform.node()}",
            f"CPU kullanımı: %{psutil.cpu_percent(interval=0.2)} ({psutil.cpu_count()} çekirdek)",
            f"RAM: {vm.used / gb:.1f} GB / {vm.total / gb:.1f} GB (%{vm.percent} dolu)",
            f"Disk: {du.used / gb:.1f} GB / {du.total / gb:.1f} GB kullanımda, {du.free / gb:.1f} GB boş",
        ]
    )
