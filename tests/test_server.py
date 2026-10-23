import io
import json

from anonimlestirici.server import Server

from .fixtures import make_txt, make_xlsx


def talk(tmp_path, requests):
    out = io.StringIO()
    stream = io.StringIO("\n".join(json.dumps(r, ensure_ascii=False) for r in requests) + "\n")
    Server(out).run(stream)
    lines = [json.loads(l) for l in out.getvalue().splitlines()]
    return {m["id"]: m for m in lines if "event" not in m}, [m for m in lines if "event" in m]


def test_full_protocol_roundtrip(tmp_path):
    src = make_xlsx(tmp_path / "sikayetler.xlsx")
    out_dir = tmp_path / "cikti"
    out_dir.mkdir()
    replies, events = talk(tmp_path, [
        {"id": 1, "cmd": "hello"},
        {"id": 2, "cmd": "configure", "settings": {"code_format": "bracket", "exclude_terms": ["Kalite Müdürlüğü"]}},
        {"id": 3, "cmd": "analyze", "paths": [str(src)]},
    ])
    assert replies[1]["ok"] and "version" in replies[1]["result"]
    cands = replies[3]["result"]["candidates"]
    assert any(c["value"] == "Ahmet Yılmaz" and c["code"] == "[KİŞİ_1]" for c in cands)
    assert not any(c["value"] == "Kalite Müdürlüğü" for c in cands)
    assert events and events[0]["event"] == "progress"


def test_edit_and_save_and_reverse(tmp_path):
    src = make_txt(tmp_path / "not.txt")
    out_dir = tmp_path / "cikti"
    out_dir.mkdir()
    s = Server(io.StringIO())
    res = s.cmd_analyze({"paths": [str(src)]}, lambda *a: None)
    birim = next(c for c in res["candidates"] if c["type"] == "BİRİM")
    res = s.cmd_set_accepted({"ids": [birim["id"]], "accepted": False}, None)
    assert next(c for c in res["candidates"] if c["id"] == birim["id"])["code"] == ""
    res = s.cmd_add_manual({"value": "Toplantı notu", "type": "ÖZEL"}, None)
    assert res["addedCount"] == 1
    saved = s.cmd_save({"outDir": str(out_dir)}, lambda *a: None)
    text = open(saved["outputs"][0], encoding="utf-8").read()
    assert "Kalite Müdürlüğü" in text and "Ahmet" not in text
    rev = s.cmd_reverse_text({"text": "Sorumlu: [KİŞİ_1] ve [KİŞİ_7]", "mappingPath": saved["mapping"]}, None)
    assert rev["text"] == "Sorumlu: Ahmet Yılmaz ve [KİŞİ_7]"
    assert rev["spans"][0] == {"start": 9, "end": 17, "replacement": "Ahmet Yılmaz"}
    assert rev["unknown"] == ["[KİŞİ_7]"]


def test_errors_are_reported_not_raised(tmp_path):
    replies, _ = talk(tmp_path, [{"id": 1, "cmd": "analyze", "paths": [str(tmp_path / "yok.docx")]}, {"id": 2, "cmd": "nope"}])
    assert replies[1]["ok"] is False and replies[1]["error"]
    assert replies[2]["ok"] is False
