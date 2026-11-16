"""Windows arayüzünün Python tarafı (pencere açmadan, sahte diyaloglarla)."""

from anonimlestirici.desktop import prefs as P
from anonimlestirici.desktop.app import Api
from anonimlestirici.desktop.selftest import run as selftest

from .fixtures import make_txt, make_xlsx


def dialogs_returning(folder):
    def fake(kind, **kw):
        return [str(folder)] if kind == "folder" else []

    return fake


def test_prefs_roundtrip_and_engine_settings():
    p = P.load()
    assert p["codeFormat"] == "bracket" and p["askOutputFolder"] is True
    p["enabled"] = {"BİRİM": False}
    p["excludeTerms"] = ["Kalite Müdürlüğü"]
    P.save(p)
    q = P.load()
    eng = P.engine_settings(q)
    assert eng["enabled"]["BİRİM"] is False and eng["enabled"]["KİŞİ"] is True
    assert eng["exclude_terms"] == ["Kalite Müdürlüğü"]
    assert eng["llm"] == {"enabled": False}
    assert eng["headers"]["ad soyad"] == "KİŞİ"


def test_api_full_flow(tmp_path):
    out = tmp_path / "cikti"
    out.mkdir()
    api = Api(dialogs=dialogs_returning(out))
    assert api.hello()["ok"]
    src = make_xlsx(tmp_path / "sikayetler.xlsx")
    r = api.analyze([str(src), str(tmp_path / "eski.doc")])
    assert r["ok"] and any(c["value"] == "Ahmet Yılmaz" for c in r["candidates"])
    assert r["problems"] and "eski.doc" in r["problems"][0]
    birim = next(c for c in r["candidates"] if c["value"] == "Satın Alma Birimi")
    r = api.exclude(birim["id"], birim["value"])
    assert "Satın Alma Birimi" in P.load()["excludeTerms"]
    saved = api.save()
    assert saved["ok"] and len(saved["outputs"]) == 1
    assert P.load()["recent"][0]["name"] == "sikayetler_anonim.xlsx"
    m = api.server.cmd_read_mapping({"path": saved["mapping"]}, None)
    assert m["count"] > 0
    rev = api.reverse_text("[KİŞİ_1] aradı", saved["mapping"])
    assert rev["text"] == "Ahmet Yılmaz aradı"


def test_api_rejects_unsupported_only(tmp_path):
    api = Api(dialogs=dialogs_returning(tmp_path))
    r = api.analyze([str(tmp_path / "rapor.pdf")])
    assert not r["ok"] and "PDF" in r["error"]


def test_save_cancelled_when_no_folder_chosen(tmp_path):
    api = Api(dialogs=lambda kind, **kw: None)
    api.analyze([str(make_txt(tmp_path / "not.txt"))])
    assert api.save() == {"ok": False, "cancelled": True}


def test_selftest_writes_log(tmp_path):
    log = tmp_path / "ozt.log"
    code = selftest(str(log))
    text = log.read_text(encoding="utf-8")
    assert "öz-test başlıyor" in text
    # dil modeli yoksa (CI'da Linux) BAŞARISIZ olur ama hata vermeden kayıt yazar
    assert ("SONUÇ: BAŞARILI" in text) == (code == 0)
