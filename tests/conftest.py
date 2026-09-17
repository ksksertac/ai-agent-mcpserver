import pytest

from local_llm.config import settings


@pytest.fixture(autouse=True)
def notes_tmp(tmp_path, monkeypatch):
    """Testler gerçek .notes.json dosyasına dokunmasın."""
    monkeypatch.setattr(settings, "notes_file", tmp_path / "notes.json")
