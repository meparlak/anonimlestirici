import pytest

from anonimlestirici.core.detectors.ner import NerDetector, ner_available
from anonimlestirici.core.engine import Session
from anonimlestirici.core.types import EntityType as T
from anonimlestirici.core.types import Segment

pytestmark = pytest.mark.skipif(not ner_available(), reason="NER modeli yok (packaging/fetch_model.sh)")

SENTENCE = "Kıvılcım Aras ile John Smith toplantıya katıldı; Yıldız Makine A.Ş. temsilcisi de oradaydı."


def test_ner_finds_names_not_in_dictionary(settings):
    d = NerDetector(settings)
    seg = Segment(SENTENCE, "x")
    d.prepare([seg])
    found = {(f.etype, f.text) for f in d.detect(seg)}
    assert (T.KISI, "Kıvılcım Aras") in found
    assert (T.KISI, "John Smith") in found
    assert (T.KURUM, "Yıldız Makine A.Ş.") in found


def test_ner_runs_inside_engine(settings, tmp_path):
    src = tmp_path / "not.txt"
    src.write_text(SENTENCE + "\n", encoding="utf-8")
    s = Session(settings)
    result = s.analyze([src])
    smith = next(c for c in result.candidates if c.value == "John Smith")
    assert "NER modeli" in smith.sources and smith.accepted


def test_ner_can_be_switched_off(settings, tmp_path):
    settings.ner_enabled = False
    src = tmp_path / "not.txt"
    src.write_text(SENTENCE + "\n", encoding="utf-8")
    result = Session(settings).analyze([src])
    assert not any("NER modeli" in c.sources for c in result.candidates)


def test_decode_with_title_and_odd_spacing(settings):
    """Unvan ismin içine düşse ve kelimeler arasında satır sonu/çift boşluk olsa da hata vermemeli."""
    import re
    from types import SimpleNamespace

    import numpy as np

    text = "Görüşen: Ahmet  Yılmaz\nBey, Dr.\nElif   Demir"
    words = [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]
    labels = ["O", "B-KISI_AD_SOYAD", "I-KISI_AD_SOYAD", "I-KISI_AD_SOYAD", "B-KISI_AD_SOYAD", "I-KISI_AD_SOYAD", "I-KISI_AD_SOYAD"]
    id2label = {0: "O", 1: "B-KISI_AD_SOYAD", 2: "I-KISI_AD_SOYAD"}
    ids = {v: k for k, v in id2label.items()}
    logits = np.zeros((len(words) + 2, 3))
    for i, lab in enumerate(labels):
        logits[i + 1, ids[lab]] = 10
    enc = SimpleNamespace(word_ids=[None] + list(range(len(words))) + [None])
    found = NerDetector(settings)._decode(text, words, enc, logits, id2label)
    assert [text[f.start : f.end] for f in found] == ["Ahmet  Yılmaz", "Elif   Demir"]
    assert [f.text for f in found] == ["Ahmet  Yılmaz", "Elif   Demir"]


def test_engine_survives_a_failing_detector(settings, tmp_path, monkeypatch):
    from anonimlestirici.core.detectors.names import NameDetector

    def boom(self, segment):
        raise ValueError("substring not found")

    monkeypatch.setattr(NameDetector, "detect", boom)
    src = tmp_path / "not.txt"
    src.write_text("Ahmet Yılmaz 0532 123 45 67 numaralı telefondan aradı.\n", encoding="utf-8")
    result = Session(settings).analyze([src])
    assert any(c.value == "0532 123 45 67" for c in result.candidates)
    assert any("Ad sözlüğü" in w for w in result.warnings)
