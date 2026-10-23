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
