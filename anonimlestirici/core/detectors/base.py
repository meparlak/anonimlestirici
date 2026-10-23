"""Dedektör arayüzü.

Her dedektör bir metin parçasını alır ve bulduğu değerleri döndürür. Yeni bir yöntem
(Türkçe NER modeli, yerel LLM...) eklemek için bu sınıftan türetip
`anonimlestirici.core.detectors.build_detectors` listesine eklemek yeterlidir.
"""

from __future__ import annotations

from ..settings import Settings
from ..types import EntityType, Finding, Segment


class Detector:
    name: str = "Dedektör"
    # Bu dedektörün üretebileceği türler; hepsi kapalıysa dedektör çalıştırılmaz.
    types: tuple[EntityType, ...] = ()

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def active(self) -> bool:
        return any(self.settings.is_enabled(t) for t in self.types)

    def detect(self, segment: Segment) -> list[Finding]:
        raise NotImplementedError

    def finding(self, m_start: int, m_end: int, text: str, et: EntityType, conf: float) -> Finding | None:
        if not self.settings.is_enabled(et):
            return None
        return Finding(m_start, m_end, text, et, conf, self.name)
