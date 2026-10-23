import json

from anonimlestirici.core.detectors.llm import OllamaDetector, is_local
from anonimlestirici.core.types import EntityType as T
from anonimlestirici.core.types import Segment

TEXT = "Hat-3'teki ustabaşının eşi Gülşah, dün fabrikaya gelip vardiya düzenini sordu ve şikâyet etti."


def fake_transport(answer):
    calls = []

    def post(url, payload, timeout):
        calls.append((url, payload))
        return {"response": json.dumps(answer)}

    return post, calls


def test_llm_is_off_by_default(settings):
    assert not OllamaDetector(settings).active


def test_llm_suggestions_are_low_confidence_and_must_exist_in_text(settings):
    settings.llm.enabled = True
    post, calls = fake_transport({"bulgular": [{"metin": "Gülşah", "tur": "KİŞİ"}, {"metin": "Uydurma Kişi", "tur": "KİŞİ"}]})
    det = OllamaDetector(settings, transport=post)
    assert det.active
    found = det.detect(Segment(TEXT, "x"))
    assert [(f.etype, f.text) for f in found] == [(T.KISI, "Gülşah")]
    assert found[0].confidence < 0.5  # onay bekler
    assert calls[0][0] == "http://localhost:11434/api/generate"


def test_llm_refuses_remote_server_without_consent(settings):
    settings.llm.enabled = True
    settings.llm.url = "http://192.0.2.10:11434"
    assert not is_local(settings.llm.url)
    assert not OllamaDetector(settings).active


def test_llm_skips_short_text(settings):
    settings.llm.enabled = True
    post, calls = fake_transport({"bulgular": []})
    OllamaDetector(settings, transport=post).detect(Segment("Ahmet Yılmaz", "x"))
    assert calls == []
