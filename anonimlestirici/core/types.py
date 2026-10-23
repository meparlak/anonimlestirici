"""Motorun ortak veri tipleri."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import Enum

_uids = itertools.count(1)


class EntityType(str, Enum):
    KISI = "KİŞİ"
    TC = "TC"
    TELEFON = "TELEFON"
    EPOSTA = "EPOSTA"
    ADRES = "ADRES"
    BIRIM = "BİRİM"
    KURUM = "KURUM"
    IBAN = "IBAN"
    PLAKA = "PLAKA"
    TARIH = "TARİH"
    VERGI = "VERGİ"
    FINANS = "FİNANS"
    BELGE = "BELGE"
    IP = "IP"
    SAGLIK = "SAĞLIK"
    HASSAS = "HASSAS"
    OZEL = "ÖZEL"

    @property
    def label(self) -> str:
        return LABELS[self]

    @classmethod
    def parse(cls, text: str) -> "EntityType":
        """'kişi', 'KISI', 'Ad soyad' gibi yazımları türe çevirir."""
        from .textutil import fold

        key = fold(text)
        for et in cls:
            if key in (fold(et.value), fold(et.name), fold(LABELS[et])):
                return et
        raise ValueError(f"Bilinmeyen tür: {text}")


LABELS = {
    EntityType.KISI: "Ad soyad",
    EntityType.TC: "TC kimlik no",
    EntityType.TELEFON: "Telefon",
    EntityType.EPOSTA: "E-posta",
    EntityType.ADRES: "Adres",
    EntityType.BIRIM: "Birim",
    EntityType.KURUM: "Kurum",
    EntityType.IBAN: "IBAN",
    EntityType.PLAKA: "Plaka",
    EntityType.TARIH: "Tarih",
    EntityType.VERGI: "Vergi/MERSİS no",
    EntityType.FINANS: "Kart/hesap no",
    EntityType.BELGE: "Belge no",
    EntityType.IP: "IP adresi",
    EntityType.SAGLIK: "Sağlık bilgisi",
    EntityType.HASSAS: "Din/etnik/siyasi",
    EntityType.OZEL: "Özel liste",
}

# Çakışan bulgularda hangisinin kazanacağı (büyük olan kazanır).
PRIORITY = {
    EntityType.OZEL: 100,
    EntityType.EPOSTA: 90,
    EntityType.IBAN: 90,
    EntityType.TC: 90,
    EntityType.TELEFON: 85,
    EntityType.FINANS: 88,
    EntityType.VERGI: 85,
    EntityType.BELGE: 85,
    EntityType.IP: 85,
    EntityType.SAGLIK: 45,
    EntityType.HASSAS: 45,
    EntityType.ADRES: 70,
    EntityType.PLAKA: 60,
    EntityType.TARIH: 60,
    EntityType.KURUM: 50,
    EntityType.BIRIM: 50,
    EntityType.KISI: 40,
}


@dataclass
class Segment:
    """Dosyadan çıkarılmış tek bir metin parçası (hücre, paragraf, satır)."""

    text: str
    location: str
    # Excel/CSV sütun başlığından ya da belge meta verisinden gelen tür ipucu.
    hint: EntityType | None = None
    # Değer tek bir bütün olarak mı ele alınmalı (hücre, yazar adı gibi)?
    whole: bool = False


@dataclass
class Finding:
    """Bir dedektörün metin parçasında bulduğu tek bir değer."""

    start: int
    end: int
    text: str
    etype: EntityType
    confidence: float
    source: str

    @property
    def score(self) -> tuple:
        return (PRIORITY[self.etype], self.end - self.start, self.confidence)


@dataclass
class Occurrence:
    file: str
    location: str
    context: str  # değerin geçtiği metin (kısaltılmış)
    start: int  # context içindeki konum
    end: int
    order: int = 0  # dosyalar boyunca metin parçasının sırası


@dataclass
class Candidate:
    """Önizlemede bir satır: aynı değerin bütün geçişleri."""

    etype: EntityType
    key: str
    value: str  # gösterilen (ilk görülen) yazım
    variants: set[str] = field(default_factory=set)
    occurrences: list[Occurrence] = field(default_factory=list)
    sources: set[str] = field(default_factory=set)
    confidence: float = 0.0
    accepted: bool = True
    code: str = ""
    manual: bool = False
    uid: int = field(default_factory=lambda: next(_uids))

    @property
    def count(self) -> int:
        return len(self.occurrences)

    @property
    def files(self) -> list[str]:
        seen: list[str] = []
        for o in self.occurrences:
            if o.file not in seen:
                seen.append(o.file)
        return seen

    @property
    def low_confidence(self) -> bool:
        return self.confidence < 0.5
