import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from local_llm.mcp_server.server import mcp
from local_llm.mcp_server.tools.files import dosya_ara, dosya_oku
from local_llm.mcp_server.tools.notes import not_kaydet, notlari_getir
from local_llm.mcp_server.tools.system import sistem_bilgisi

EXPECTED_TOOLS = {"sistem_bilgisi", "dosya_ara", "dosya_oku", "not_kaydet", "notlari_getir"}


def test_sistem_bilgisi_icerik():
    out = sistem_bilgisi()
    assert "Saat:" in out and "RAM:" in out and "Disk:" in out


def test_dosya_ara_bulur():
    out = dosya_ara("pyproject.toml")
    assert "pyproject.toml" in out


def test_dosya_ara_glob():
    assert "CLAUDE.md" in dosya_ara("*.md")


def test_dosya_oku():
    assert "[project]" in dosya_oku("pyproject.toml")


def test_dosya_oku_yok():
    assert "bulunamadı" in dosya_oku("yok_boyle_dosya.txt")


def test_dosya_oku_proje_disi_engellenir():
    with pytest.raises(ValueError):
        dosya_oku("../../secret.txt")


def test_notlar_bos_sonra_kayit():
    assert notlari_getir() == "Kayıtlı not yok."
    assert "#1" in not_kaydet("süt al")
    assert "süt al" in notlari_getir()


def test_docstringler_ne_zaman_kullan_formatinda():
    for fn in (sistem_bilgisi, dosya_ara, dosya_oku, not_kaydet, notlari_getir):
        assert "NE ZAMAN KULLAN:" in fn.__doc__ and "NE ZAMAN KULLANMA:" in fn.__doc__


async def test_tool_listesi_kayitli():
    names = {t.name for t in await mcp.list_tools()}
    assert names == EXPECTED_TOOLS


async def test_stdio_uzerinden_mcp_protokolu():
    """Gerçek MCP: sunucuyu subprocess olarak başlat, tools/list ve tools/call yap."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "local_llm.mcp_server.server"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == EXPECTED_TOOLS
            res = await session.call_tool("dosya_ara", {"desen": "pyproject.toml"})
            assert "pyproject.toml" in res.content[0].text
