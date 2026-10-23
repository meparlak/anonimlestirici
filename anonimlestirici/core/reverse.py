"""Geri çevirme: yapay zekânın cevabındaki kodları eşleştirme tablosuyla gerçek değerlere çevirir."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .engine import Span, unique_path
from .formats import open_document
from .report import read_mapping
from .settings import Settings
from .textutil import ci_pattern, fold
from .types import EntityType

# Yapay zekâ kodu biraz değiştirebilir: [KİŞİ_1], KİŞİ_1, [Kişi_1], KISI 1, [KİŞİ-1]
_TYPE_ALT = "|".join(
    sorted({ci_pattern(et.value) for et in EntityType} | {ci_pattern(et.name) for et in EntityType}, key=len, reverse=True)
)
_CODE = re.compile(
    r"\[?\s*(?P<type>" + _TYPE_ALT + r")[\s_-]?(?P<num>\d+)\s*\]?"
    r"|(?P<word>Kişi|Telefon|E-posta|Adres|Birim|Kurum|Iban|Tc|Plaka|Tarih|Vergi|Finans|Belge|Ip|Sağlık|Hassas|Özel)"
    r"\s(?P<letter>[A-Z]{1,3})\b",
    re.IGNORECASE,
)
_TYPE_OF = {fold(et.value): et for et in EntityType} | {fold(et.name): et for et in EntityType}


def _code_key(m: re.Match) -> str | None:
    if m.group("type"):
        et = _TYPE_OF.get(fold(m.group("type")))
        return f"{et.value}_{int(m.group('num'))}" if et else None
    word = fold(m.group("word"))
    return f"L:{word}:{m.group('letter').upper()}"


def _norm_mapping(mapping: dict[str, str]) -> dict[str, str]:
    out = {}
    for code, value in mapping.items():
        m = _CODE.fullmatch(code.strip())
        if m:
            k = _code_key(m)
            if k:
                out[k] = value
    return out


@dataclass
class ReverseStats:
    replaced: int = 0
    unknown: set[str] | None = None


class ReverseReplacer:
    def __init__(self, mapping: dict[str, str]):
        self.mapping = _norm_mapping(mapping)
        self.stats = ReverseStats(0, set())

    def spans(self, text: str, segment=None) -> list[Span]:
        out = []
        for m in _CODE.finditer(text):
            # yalnızca köşeli parantezli ya da alt çizgili/harfli kodlar; düz "Kurum 2" gibi ifadeleri atla
            raw = m.group()
            if m.group("type") and "[" not in raw and "_" not in raw and "-" not in raw:
                continue
            k = _code_key(m)
            if k and k in self.mapping:
                out.append(Span(m.start(), m.end(), self.mapping[k]))
                self.stats.replaced += 1
            elif m.group("type"):
                self.stats.unknown.add(raw.strip())
        return out

    def apply(self, text: str, segment=None) -> str:
        for sp in sorted(self.spans(text, segment), key=lambda s: s.start, reverse=True):
            text = text[: sp.start] + sp.replacement + text[sp.end :]
        return text


def reverse_text(text: str, mapping_path: Path) -> tuple[str, ReverseStats]:
    r = ReverseReplacer(read_mapping(mapping_path))
    return r.apply(text), r.stats


def reverse_file(path: Path, mapping_path: Path, out_dir: Path | None = None) -> tuple[Path, ReverseStats]:
    settings = Settings()
    settings.clean_metadata = False
    doc = open_document(Path(path), settings)
    r = ReverseReplacer(read_mapping(mapping_path))
    out = unique_path((out_dir or doc.path.parent) / f"{doc.path.stem}_geri_cevrilmis{doc.path.suffix}")
    doc.save(out, r)
    return out, r.stats
