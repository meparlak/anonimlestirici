from ..settings import Settings
from .address import AddressDetector
from .base import Detector
from .custom import ColumnHintDetector, CustomListDetector
from .llm import OllamaDetector
from .names import NameDetector
from .ner import NerDetector
from .orgs import OrgDetector
from .patterns import PatternDetector


def build_detectors(settings: Settings) -> list[Detector]:
    """Çalıştırılacak dedektörler. Yeni bir yöntem eklemek için listeye ekleyin."""
    detectors: list[Detector] = [
        CustomListDetector(settings),
        ColumnHintDetector(settings),
        PatternDetector(settings),
        AddressDetector(settings),
        OrgDetector(settings),
        NameDetector(settings),
        NerDetector(settings),
        OllamaDetector(settings),
    ]
    return [d for d in detectors if d.active]


__all__ = ["Detector", "build_detectors"]
