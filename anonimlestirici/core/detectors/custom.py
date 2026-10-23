"""Kullanıcının listesi ve sütun başlığı ipuçları."""

from __future__ import annotations

import re

from ..textutil import bounded, ci_pattern
from ..types import EntityType, Finding, Segment
from .base import Detector


class CustomListDetector(Detector):
    name = "Özel liste"
    types = tuple(EntityType)

    def __init__(self, settings):
        super().__init__(settings)
        entries = sorted(settings.custom_entries(), key=lambda x: -len(x[0]))
        self._rx = [(re.compile(bounded(ci_pattern(term))), et) for term, et in entries]

    @property
    def active(self) -> bool:
        return bool(self._rx)

    def detect(self, segment: Segment) -> list[Finding]:
        out = []
        for rx, et in self._rx:
            for m in rx.finditer(segment.text):
                out.append(Finding(m.start(), m.end(), m.group(), et, 1.0, self.name))
        return out


class ColumnHintDetector(Detector):
    """Excel/CSV'de "Ad Soyad", "Telefon" gibi başlıklı sütunlardaki hücrenin tamamını işaretler.

    Belge meta verisi (yazar, son değiştiren) de bu yolla KİŞİ olarak gelir.
    """

    name = "Sütun başlığı"
    types = tuple(EntityType)

    def detect(self, segment: Segment) -> list[Finding]:
        if segment.hint is None or not segment.whole or not self.settings.is_enabled(segment.hint):
            return []
        text = segment.text
        stripped = text.strip()
        if not stripped or len(stripped) > 200:
            return []
        if segment.hint in (EntityType.KISI, EntityType.KURUM, EntityType.BIRIM) and not re.search(r"[^\W\d_]", stripped):
            return []  # yalnızca sayı/işaret olan hücreler isim değildir
        s = text.index(stripped)
        # Hücre konumu ("Sayfa1!B2", "C5") değilse değer belge bilgisinden (yazar, yorum yazarı) gelmiştir
        is_cell = "!" in segment.location or re.fullmatch(r"[A-Z]+\d+", segment.location)
        source = self.name if is_cell else "Belge bilgisi"
        return [Finding(s, s + len(stripped), stripped, segment.hint, 1.0, source)]
