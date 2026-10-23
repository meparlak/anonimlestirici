"""Kurum ve birim adı dedektörü: büyük harfli kelime dizisi + bilinen sonek."""

from __future__ import annotations

import re

from ..textutil import LOWER, UPPER, ci_pattern, fold
from ..types import EntityType, Finding, Segment
from .base import Detector
from .names import TITLES_AFTER, TITLES_BEFORE, lexicon

# Sonek → tür. Çok kelimeli sonekler önce denenir.
SUFFIXES: list[tuple[str, EntityType]] = [
    # birimler
    ("Daire Başkanlığı", EntityType.BIRIM),
    ("Şube Müdürlüğü", EntityType.BIRIM),
    ("Anabilim Dalı", EntityType.BIRIM),
    ("Bilim Dalı", EntityType.BIRIM),
    ("Genel Sekreterliği", EntityType.BIRIM),
    ("Müdürlüğü", EntityType.BIRIM),
    ("Müdürlük", EntityType.BIRIM),
    ("Başkanlığı", EntityType.BIRIM),
    ("Birimi", EntityType.BIRIM),
    ("Bölümü", EntityType.BIRIM),
    ("Şubesi", EntityType.BIRIM),
    ("Şefliği", EntityType.BIRIM),
    ("Koordinatörlüğü", EntityType.BIRIM),
    ("Dekanlığı", EntityType.BIRIM),
    ("Sekreterliği", EntityType.BIRIM),
    ("Servisi", EntityType.BIRIM),
    ("Departmanı", EntityType.BIRIM),
    ("Ofisi", EntityType.BIRIM),
    ("Komisyonu", EntityType.BIRIM),
    ("Komitesi", EntityType.BIRIM),
    ("Kurulu", EntityType.BIRIM),
    ("Laboratuvarı", EntityType.BIRIM),
    ("Atölyesi", EntityType.BIRIM),
    ("Ekibi", EntityType.BIRIM),
    ("Fakültesi", EntityType.BIRIM),
    ("Yüksekokulu", EntityType.BIRIM),
    ("Meslek Yüksekokulu", EntityType.BIRIM),
    ("Enstitüsü", EntityType.BIRIM),
    ("Merkezi", EntityType.BIRIM),
    # kurumlar
    ("Sanayi ve Ticaret Anonim Şirketi", EntityType.KURUM),
    ("Sanayi ve Ticaret Limited Şirketi", EntityType.KURUM),
    ("San. ve Tic. A.Ş.", EntityType.KURUM),
    ("San. Tic. A.Ş.", EntityType.KURUM),
    ("San. ve Tic. Ltd. Şti.", EntityType.KURUM),
    ("San. Tic. Ltd. Şti.", EntityType.KURUM),
    ("Tic. Ltd. Şti.", EntityType.KURUM),
    ("Ltd. Şti.", EntityType.KURUM),
    ("Ltd.Şti.", EntityType.KURUM),
    ("Anonim Şirketi", EntityType.KURUM),
    ("Limited Şirketi", EntityType.KURUM),
    ("A.Ş.", EntityType.KURUM),
    ("A.Ş", EntityType.KURUM),
    ("AŞ", EntityType.KURUM),
    ("Ltd.", EntityType.KURUM),
    ("Üniversitesi", EntityType.KURUM),
    ("Bakanlığı", EntityType.KURUM),
    ("Belediyesi", EntityType.KURUM),
    ("Valiliği", EntityType.KURUM),
    ("Kaymakamlığı", EntityType.KURUM),
    ("Rektörlüğü", EntityType.KURUM),
    ("Hastanesi", EntityType.KURUM),
    ("Lisesi", EntityType.KURUM),
    ("Okulu", EntityType.KURUM),
    ("İlkokulu", EntityType.KURUM),
    ("Ortaokulu", EntityType.KURUM),
    ("Koleji", EntityType.KURUM),
    ("Vakfı", EntityType.KURUM),
    ("Derneği", EntityType.KURUM),
    ("Odası", EntityType.KURUM),
    ("Borsası", EntityType.KURUM),
    ("Birliği", EntityType.KURUM),
    ("Federasyonu", EntityType.KURUM),
    ("Sendikası", EntityType.KURUM),
    ("Kurumu", EntityType.KURUM),
    ("Ajansı", EntityType.KURUM),
    ("Holding", EntityType.KURUM),
    ("Şirketi", EntityType.KURUM),
    ("Bankası", EntityType.KURUM),
    ("Kooperatifi", EntityType.KURUM),
    ("Akademisi", EntityType.KURUM),
    ("Fabrikası", EntityType.KURUM),
    ("Grubu", EntityType.KURUM),
    ("Inc.", EntityType.KURUM),
    ("GmbH", EntityType.KURUM),
    ("LLC", EntityType.KURUM),
]

_SUFFIX_TYPES = {fold(sfx): t for sfx, t in SUFFIXES}
_SUFFIX_RX = re.compile(
    rf"(?<![{LOWER}{UPPER}])(?:"
    + "|".join(ci_pattern(sfx) for sfx, _ in sorted(SUFFIXES, key=lambda x: -len(x[0])))
    + rf")(?![{LOWER}{UPPER}])"
)
_WORD = re.compile(r"\S+")
_CAP = re.compile(rf"^(?:[{UPPER}][{LOWER}{UPPER}0-9]*\.?|[0-9]+\.?|[{UPPER}]\.(?:[{UPPER}]\.)*)$")
_CONNECTORS = {"ve", "&", "-", "de", "da"}

# Kurum adının başına yapışmaması gereken kelimeler (cümle başı, unvan, tarih)
_LEADING_DROP = {
    fold(w)
    for w in [
        "Bu", "Şu", "O", "Bir", "Ve", "İle", "Ama", "Ancak", "Fakat", "Ayrıca", "Bugün", "Dün", "Yarın",
        "Sayın", "Değerli", "T.C.", "TC", "Konu", "Ekte", "İlgi", "Not", "Ocak", "Şubat", "Mart", "Nisan",
        "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık", "Pazartesi", "Salı",
        "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar", "Hem", "Ya", "Da", "De", "Ile",
    ]
} | TITLES_BEFORE
_MAX_WORDS = 7


class OrgDetector(Detector):
    name = "Sonek kalıbı"
    types = (EntityType.KURUM, EntityType.BIRIM)

    def detect(self, segment: Segment) -> list[Finding]:
        text = segment.text
        lex = lexicon()
        out: list[Finding] = []
        for m in _SUFFIX_RX.finditer(text):
            et = _SUFFIX_TYPES.get(fold(m.group()), EntityType.KURUM)
            if not self.settings.is_enabled(et):
                continue
            before = [(w.start(), w.group()) for w in _WORD.finditer(text[: m.start()])]
            words: list[tuple[int, str]] = []
            # Sonekten geriye doğru büyük harfli kelimeleri topla
            for pos, w in reversed(before):
                opener = w.lstrip("(\"'“«[")
                if opener != w:
                    # "(Kalite Müdürlüğü)": parantezden sonraki kelime adın başıdır
                    pos += len(w) - len(opener)
                    if _CAP.match(opener) and fold(opener) not in _SUFFIX_TYPES:
                        words.append((pos, opener))
                    break
                core = w.rstrip(",;:")
                if core != w or (w.endswith(".") and len(w) > 5):
                    break  # virgül ya da cümle sonu: önceki parça
                fw = fold(core.rstrip("."))
                if fw in _CONNECTORS:
                    words.append((pos, w))
                    continue
                if not _CAP.match(core) or fw in _SUFFIX_TYPES or fold(core) in _SUFFIX_TYPES:
                    break
                if len(words) >= _MAX_WORDS:
                    break
                words.append((pos, w))
            words.reverse()
            # baştaki bağlaç ve cümle başı kelimelerini at
            while words and (fold(words[0][1].rstrip(".")) in _LEADING_DROP or fold(words[0][1]) in _CONNECTORS):
                words.pop(0)
            if et == EntityType.BIRIM:
                # "Ahmet Yılmaz Kalite Müdürlüğü": kişi adını birime katma
                cut = -1
                for i, (_, w) in enumerate(words):
                    fw = fold(w)
                    if (fw in lex["first"] and fw not in lex["ambiguous"]) or fw in TITLES_AFTER:
                        cut = i
                if cut >= 0:
                    if cut + 1 < len(words) and fold(words[cut + 1][1]) in lex["surname"]:
                        cut += 1
                    words = words[cut + 1 :]
            if not words:
                continue
            s = words[0][0]
            frag = text[s : m.end()]
            f = self.finding(s, m.end(), frag, et, 0.85)
            if f:
                out.append(f)
        return out
