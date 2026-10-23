import pytest

from anonimlestirici.core.settings import Settings


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Testler kullanıcının gerçek ayar dosyasına dokunmasın."""
    monkeypatch.setenv("ANONIMLESTIRICI_HOME", str(tmp_path / "home"))


@pytest.fixture
def settings():
    return Settings()
