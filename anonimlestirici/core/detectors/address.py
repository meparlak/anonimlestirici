"""Adres dedektörü: Mah., Cad., Sok., No: gibi ipuçlarının etrafındaki adres parçasını bulur."""

from __future__ import annotations

import re

from ..textutil import fold
from ..types import EntityType, Finding, Segment
from .base import Detector
from .names import lexicon

ANCHORS = {
    fold(w)
    for w in [
        "Mahallesi", "Mah", "Mah.", "Mh.", "Mh", "Caddesi", "Cad", "Cad.", "Cd.", "Cd", "Sokak", "Sokağı",
        "Sok", "Sok.", "Sk.", "Sk", "Bulvarı", "Blv.", "Bulv.", "Apartmanı", "Apt", "Apt.", "Sitesi",
        "Blok", "Blk.", "Köyü", "Mevkii", "Mevkisi", "OSB", "Küme", "Evleri", "Konutları", "Yolu", "İş",
        "Merkezi", "Plaza", "Han", "Hanı", "Pasajı",
    ]
}
STRONG = {fold(w) for w in ["Mahallesi", "Mah", "Mah.", "Mh.", "Mh", "Caddesi", "Cad", "Cad.", "Cd.", "Cd",
                            "Sokak", "Sokağı", "Sok", "Sok.", "Sk.", "Sk", "Bulvarı", "Blv.", "Bulv.", "OSB",
                            "Köyü", "Apartmanı", "Apt", "Apt."]}

_NUM_TOKEN = re.compile(r"^(?:(?:No|Kat|Daire|D|K|Blok|PK|P\.K)\s?[:.]?\s?)?\d+[A-Za-z]?(?:[/-]\d+[A-Za-z]?)?[,.]?$", re.I)
_NUM_LABEL = re.compile(r"^(?:No|Kat|Daire|D|K|PK|P\.K\.?)[:.]?$", re.I)
_PLACE_SLASH = re.compile(r"^[A-ZÇĞİÖŞÜ][\wçğıöşü]+/[A-ZÇĞİÖŞÜ][\wçğıöşü]+[,.]?$")
_TOKENS = re.compile(r"\S+")


class AddressDetector(Detector):
    name = "Adres ipuçları"
    types = (EntityType.ADRES,)

    def detect(self, segment: Segment) -> list[Finding]:
        if not self.settings.is_enabled(EntityType.ADRES):
            return []
        text = segment.text
        toks = [(m.start(), m.end(), m.group()) for m in _TOKENS.finditer(text)]
        cities = lexicon()["city"]
        out: list[Finding] = []

        def kind(tok: str) -> str:
            core = tok.rstrip(",;")
            f = fold(core)
            f_nodot = f.rstrip(".")
            if f in ANCHORS or f_nodot in ANCHORS:
                return "anchor"
            if _NUM_TOKEN.match(core) or _NUM_LABEL.match(core):
                return "num"
            if _PLACE_SLASH.match(core):
                return "place"
            if re.fullmatch(r"\d{5}", core):
                return "num"
            if core[:1].isupper() or core[:1].isdigit():
                return "cap"
            return "other"

        kinds = [kind(t[2]) for t in toks]
        i = 0
        n = len(toks)
        while i < n:
            if kinds[i] != "anchor" or fold(toks[i][2].rstrip(",;.")) not in {a.rstrip(".") for a in STRONG}:
                i += 1
                continue
            # geriye doğru: anchor öncesindeki en fazla 3 büyük harfli kelime (Esentepe Mah.)
            s = i
            back = 0
            while s - 1 >= 0 and kinds[s - 1] in ("cap", "num") and back < 3 and not toks[s - 1][2].endswith((".", ",", ":")):
                if fold(toks[s - 1][2]) in {"sayin", "adres", "adresi"}:
                    break
                s -= 1
                back += 1
            # ileriye doğru: adres sözcükleri, numaralar, büyük harfli kelimeler
            e = i
            anchors = 1
            has_num = False
            trailing_caps = 0
            while e + 1 < n:
                k = kinds[e + 1]
                tok = toks[e + 1][2]
                if k == "anchor":
                    anchors += 1
                    trailing_caps = 0
                elif k == "num":
                    has_num = True
                    trailing_caps = 0
                elif k == "place":
                    e += 1
                    break
                elif k == "cap":
                    core = fold(tok.rstrip(",;."))
                    if trailing_caps >= 3 and core not in cities:
                        break
                    trailing_caps += 1
                else:
                    break
                e += 1
                if tok.endswith(".") and k not in ("anchor",) and not _NUM_LABEL.match(tok) and len(tok) > 3:
                    break  # cümle sonu
            # sondaki il/ilçe olmayan büyük harfli kelimeleri bırak (sonraki cümlenin başı olabilir)
            while e > i and kinds[e] == "cap" and fold(toks[e][2].rstrip(",;.")) not in cities:
                prev = toks[e - 1][2]
                if prev.endswith(",") or kinds[e - 1] in ("num",):
                    # "No:12 Serdivan, Sakarya" → ilçe olabilir, tut
                    if fold(toks[e][2].rstrip(",;.")) in cities or (e + 1 < n and kinds[e + 1] == "place"):
                        break
                e -= 1
            # 5 haneli posta kodu
            if e + 1 < n and re.fullmatch(r"\d{5}[,.]?", toks[e + 1][2]):
                e += 1
            if anchors >= 2 or (anchors >= 1 and has_num):
                start = toks[s][0]
                frag = text[start : toks[e][1]].rstrip(",;. ")
                # "Mah." gibi kısaltma noktasıyla bitiyorsa noktayı geri koy
                if toks[e][2].rstrip(",;").endswith(".") and fold(toks[e][2].rstrip(",;")) in ANCHORS:
                    frag = text[start : toks[e][1]].rstrip(",; ")
                out.append(Finding(start, start + len(frag), frag, EntityType.ADRES, 0.85, self.name))
                i = e + 1
            else:
                i += 1
        return out
