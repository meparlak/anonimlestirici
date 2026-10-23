"""Türkçe varlık ismi tanıma (NER) dedektörü.

Model, uygulamanın içinde ONNX biçiminde gelir ve ONNX Runtime ile işlemcide çalışır;
internet bağlantısı ya da PyTorch gerekmez. Model klasöründe şu dosyalar bulunur:

    model.onnx       (8 bit sıkıştırılmış)
    tokenizer.json   (Hugging Face hızlı tokenizer)
    config.json      (id2label: B-PER, I-ORG ...)
    LICENSE / README (modelin lisansı ve kaynağı)

Klasör sırasıyla ANONIMLESTIRICI_NER_DIR ortam değişkeninde, paketin `models/ner` klasöründe
aranır. Bulunamazsa dedektör sessizce devre dışı kalır ve diğer yöntemler çalışmaya devam eder.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

from ..textutil import fold
from ..types import EntityType, Finding, Segment
from .base import Detector
from .names import TITLES_AFTER, TITLES_BEFORE

# Model etiketleri → uygulamanın türleri. Yer adları (LOC) ve meslek/unvan tek başına kişisel
# veri sayılmadığı için anonimleştirilmez.
LABEL_MAP = {
    # ytu-ce-cosmos/modernbert-tr-pii-ner (KVKK türleri)
    "KISI_AD_SOYAD": EntityType.KISI,
    "TUZEL_KISI": EntityType.KURUM,
    "ADRES": EntityType.ADRES,
    "POSTA_KODU": EntityType.ADRES,
    "TCKN": EntityType.TC,
    "TELEFON": EntityType.TELEFON,
    "EMAIL": EntityType.EPOSTA,
    "IBAN_TR": EntityType.IBAN,
    "HESAP_NO": EntityType.FINANS,
    "KART_NO": EntityType.FINANS,
    "KART_CVV": EntityType.FINANS,
    "KART_SON_KULLANMA": EntityType.FINANS,
    "SWIFT_BIC": EntityType.FINANS,
    "VKN": EntityType.VERGI,
    "MERSIS_NO": EntityType.VERGI,
    "ETTN_EFATURA_ID": EntityType.VERGI,
    "PASAPORT_NO": EntityType.BELGE,
    "KIMLIK_BELGE_NO": EntityType.BELGE,
    "SURUCU_BELGESI_NO": EntityType.BELGE,
    "PLAKA": EntityType.PLAKA,
    "DOGUM_TARIHI": EntityType.TARIH,
    "IP_ADRES": EntityType.IP,
    "SAGLIK_BILGISI": EntityType.SAGLIK,
    "DIN_ETNIK_SIYASI_TERIM": EntityType.HASSAS,
    # genel NER modelleri
    "PER": EntityType.KISI,
    "PERSON": EntityType.KISI,
    "ORG": EntityType.KURUM,
    "ORGANIZATION": EntityType.KURUM,
}

MAX_TOKENS = 512
CHUNK_CHARS = 1200  # uzun metinler cümle sınırlarından bu boyda parçalara bölünür
BATCH = 16


def model_dir() -> Path | None:
    candidates = []
    env = os.environ.get("ANONIMLESTIRICI_NER_DIR")
    if env:
        candidates.append(Path(env))
    here = Path(__file__).resolve().parent.parent.parent  # anonimlestirici/
    candidates.append(here / "models" / "ner")
    if getattr(sys, "_MEIPASS", None):  # PyInstaller paketi
        candidates.append(Path(sys._MEIPASS) / "anonimlestirici" / "models" / "ner")
    for c in candidates:
        if (c / "model.onnx").is_file() and (c / "tokenizer.json").is_file() and (c / "config.json").is_file():
            return c
    return None


def ner_available() -> bool:
    if model_dir() is None:
        return False
    try:
        import onnxruntime  # noqa: F401
        import tokenizers  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _load(path: str):
    import onnxruntime as ort
    from tokenizers import Tokenizer

    p = Path(path)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = max(1, (os.cpu_count() or 4) - 1)
    opts.log_severity_level = 3
    session = ort.InferenceSession(str(p / "model.onnx"), opts, providers=["CPUExecutionProvider"])
    tok = Tokenizer.from_file(str(p / "tokenizer.json"))
    tok.no_padding()
    tok.enable_truncation(MAX_TOKENS)
    cfg = json.loads((p / "config.json").read_text(encoding="utf-8"))
    id2label = {int(k): v for k, v in cfg["id2label"].items()}
    input_names = {i.name for i in session.get_inputs()}
    return session, tok, id2label, input_names


def _entity(label: str) -> tuple[str, str]:
    """'B-PER' → ('B', 'PER'); 'O' → ('O', '')"""
    if label == "O" or "-" not in label:
        return "O", ""
    prefix, _, ent = label.partition("-")
    return prefix.upper(), ent.upper()


def _split(text: str) -> list[tuple[str, int]]:
    """Uzun metni cümle sonlarından CHUNK_CHARS boyunu aşmayan parçalara böler."""
    if len(text) <= CHUNK_CHARS:
        return [(text, 0)]
    out, start = [], 0
    while start < len(text):
        end = min(len(text), start + CHUNK_CHARS)
        if end < len(text):
            cut = max(text.rfind(". ", start, end), text.rfind("\n", start, end))
            if cut > start + CHUNK_CHARS // 3:
                end = cut + 1
        out.append((text[start:end], start))
        start = end
    return out


def _softmax(row: list[float]) -> list[float]:
    m = max(row)
    exps = [math.exp(x - m) for x in row]
    s = sum(exps)
    return [e / s for e in exps]


class NerDetector(Detector):
    name = "NER modeli"
    types = tuple(dict.fromkeys(LABEL_MAP.values()))

    def __init__(self, settings):
        super().__init__(settings)
        self.dir = model_dir() if settings.ner_enabled else None
        self.cache: dict[int, list[Finding]] = {}

    @property
    def active(self) -> bool:
        return self.dir is not None and ner_available() and super().active

    @staticmethod
    def worth_checking(seg: Segment) -> bool:
        t = seg.text.strip()
        # Sütun başlığından türü zaten belli olan hücreler ve tek kelimelik kısa metinler atlanır;
        # harf içermeyen metinler kalıp dedektörüne kalır.
        if seg.hint is not None and seg.whole:
            return False
        return len(t) >= 3 and " " in t and re.search(r"[^\W\d_]", t) is not None

    def prepare(self, segments: list[Segment], progress=None, cancel=None) -> None:
        import numpy as np

        session, tok, id2label, input_names = _load(str(self.dir))
        todo = [s for s in segments if self.worth_checking(s)]
        # Aynı metin (ör. Excel'de tekrar eden hücreler) bir kez işlenir
        unique: dict[str, list[Segment]] = {}
        for s in todo:
            unique.setdefault(s.text, []).append(s)
        # Uzun metinleri parçalara böl: (metin, parça, parçanın başlangıcı)
        chunks: list[tuple[str, str, int]] = []
        for text in unique:
            for piece, offset in _split(text):
                chunks.append((text, piece, offset))
        chunks.sort(key=lambda c: len(c[1]))
        results: dict[str, list[Finding]] = {t: [] for t in unique}
        for b in range(0, len(chunks), BATCH):
            if cancel and cancel():
                from ..engine import Cancelled

                raise Cancelled()
            if progress:
                progress(b, len(chunks), "Dil modeliyle kişisel veriler aranıyor")
            group = chunks[b : b + BATCH]
            # Model boşlukla ayrılmış kelimeler üzerinde eğitildi; her kelimenin etiketi ilk alt parçasından okunur
            words = [[(m.start(), m.end()) for m in re.finditer(r"\S+", c[1])] for c in group]
            encs = tok.encode_batch([[c[1][a:b] for a, b in w] for c, w in zip(group, words)], is_pretokenized=True)
            width = max(len(e.ids) for e in encs)
            ids = np.zeros((len(encs), width), dtype=np.int64)
            mask = np.zeros((len(encs), width), dtype=np.int64)
            for i, e in enumerate(encs):
                ids[i, : len(e.ids)] = e.ids
                mask[i, : len(e.ids)] = 1
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in input_names:
                feed["token_type_ids"] = np.zeros_like(ids)
            logits = session.run(None, feed)[0]
            for i, ((text, piece, offset), e) in enumerate(zip(group, encs)):
                for f in self._decode(piece, words[i], e, logits[i], id2label):
                    f.start += offset
                    f.end += offset
                    results[text].append(f)
        for text, segs in unique.items():
            for s in segs:
                self.cache[id(s)] = results.get(text, [])

    def _decode(self, text, words, enc, logits, id2label) -> list[Finding]:
        # her kelime için ilk alt parçanın etiketi ve olasılığı
        labels: dict[int, tuple[str, str, float]] = {}
        for t, w in enumerate(enc.word_ids):
            if w is None or w in labels:
                continue
            probs = _softmax(list(logits[t]))
            k = max(range(len(probs)), key=probs.__getitem__)
            prefix, ent = _entity(id2label.get(k, "O"))
            labels[w] = (prefix, ent, probs[k])
        spans: list[list] = []  # [tür, ilk kelime, son kelime, olasılıklar]
        for w in range(len(words)):
            prefix, ent, p = labels.get(w, ("O", "", 0.0))
            if not ent or ent not in LABEL_MAP:
                continue
            if prefix == "I" and spans and spans[-1][0] == ent and spans[-1][2] == w - 1:
                spans[-1][2] = w
                spans[-1][3].append(p)
            else:
                spans.append([ent, w, w, [p]])
        out: list[Finding] = []
        for ent, w0, w1, ps in spans:
            a, b = words[w0][0], words[w1][1]
            frag = text[a:b]
            # kelimeye yapışık noktalama ve Türkçe ekler: "Demir," → "Demir", "Kaya'ya" → "Kaya"
            frag = re.sub(r"['’][^\s'’]*$", "", frag) if LABEL_MAP[ent] in (EntityType.KISI, EntityType.KURUM) else frag
            stripped = frag.strip(" ,;:\"()[]")
            if stripped.endswith(".") and not re.search(r"\b[A-ZÇĞİÖŞÜ]\.$|A\.Ş\.$|Şti\.$|Ltd\.$", stripped):
                stripped = stripped[:-1]
            et = LABEL_MAP[ent]
            if et == EntityType.KISI:
                # unvanlar kodun dışında kalır: "Serkan Usta" → "Serkan", "Dr. Elif Demir" → "Elif Demir"
                parts = stripped.split()
                while parts and fold(parts[-1]) in TITLES_AFTER:
                    parts.pop()
                while parts and fold(parts[0]) in TITLES_BEFORE:
                    parts.pop(0)
                stripped = " ".join(parts)
            if len(stripped) < 2:
                continue
            a = text.index(stripped, a)
            if not self.settings.is_enabled(et):
                continue
            p = sum(ps) / len(ps)
            # Model kendinden çok emin değilse önizlemede işaretsiz gelir
            conf = 0.7 if p >= 0.8 else 0.45
            out.append(Finding(a, a + len(stripped), stripped, et, conf, self.name))
        return out

    def detect(self, segment: Segment) -> list[Finding]:
        return self.cache.get(id(segment), [])
