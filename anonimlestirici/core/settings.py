"""Kullanıcı ayarları. ~/Library/Application Support/Anonimlestirici/ayarlar.json içinde saklanır."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .types import EntityType

APP_DIR_NAME = "Anonimlestirici"

DEFAULT_ENABLED = {
    EntityType.KISI: True,
    EntityType.TC: True,
    EntityType.TELEFON: True,
    EntityType.EPOSTA: True,
    EntityType.ADRES: True,
    EntityType.BIRIM: True,
    EntityType.KURUM: True,
    EntityType.IBAN: True,
    EntityType.PLAKA: False,
    EntityType.TARIH: False,
    EntityType.VERGI: True,
    EntityType.FINANS: True,
    EntityType.BELGE: True,
    EntityType.IP: True,
    EntityType.SAGLIK: True,
    EntityType.HASSAS: True,
    EntityType.OZEL: True,
}

# Excel/CSV sütun başlığı → tür. Başlıklar karşılaştırılırken Türkçe harfler ve noktalama sadeleştirilir.
DEFAULT_HEADERS = {
    "ad soyad": "KİŞİ",
    "adı soyadı": "KİŞİ",
    "adi soyadi": "KİŞİ",
    "ad soyadı": "KİŞİ",
    "adsoyad": "KİŞİ",
    "isim": "KİŞİ",
    "isim soyisim": "KİŞİ",
    "ad": "KİŞİ",
    "adı": "KİŞİ",
    "soyad": "KİŞİ",
    "soyadı": "KİŞİ",
    "personel": "KİŞİ",
    "personel adı": "KİŞİ",
    "çalışan": "KİŞİ",
    "çalışan adı": "KİŞİ",
    "müşteri adı": "KİŞİ",
    "ilgili kişi": "KİŞİ",
    "yetkili": "KİŞİ",
    "yetkili kişi": "KİŞİ",
    "talep eden": "KİŞİ",
    "şikayet eden": "KİŞİ",
    "hazırlayan": "KİŞİ",
    "onaylayan": "KİŞİ",
    "denetçi": "KİŞİ",
    "tc": "TC",
    "tc no": "TC",
    "tckn": "TC",
    "tc kimlik": "TC",
    "tc kimlik no": "TC",
    "kimlik no": "TC",
    "telefon": "TELEFON",
    "tel": "TELEFON",
    "tel no": "TELEFON",
    "telefon no": "TELEFON",
    "gsm": "TELEFON",
    "cep": "TELEFON",
    "cep telefonu": "TELEFON",
    "e posta": "EPOSTA",
    "eposta": "EPOSTA",
    "e mail": "EPOSTA",
    "email": "EPOSTA",
    "mail": "EPOSTA",
    "adres": "ADRES",
    "açık adres": "ADRES",
    "ev adresi": "ADRES",
    "iş adresi": "ADRES",
    "birim": "BİRİM",
    "birimi": "BİRİM",
    "departman": "BİRİM",
    "bölüm": "BİRİM",
    "kurum": "KURUM",
    "kurum adı": "KURUM",
    "firma": "KURUM",
    "firma adı": "KURUM",
    "şirket": "KURUM",
    "tedarikçi": "KURUM",
    "iban": "IBAN",
}

CODE_FORMATS = {
    "bracket": "[KİŞİ_1]",
    "plain": "KİŞİ_1",
    "letter": "Kişi A",
}


def app_support_dir() -> Path:
    base = os.environ.get("ANONIMLESTIRICI_HOME")
    if base:
        p = Path(base)
    else:
        p = Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class LLMSettings:
    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "qwen2.5:3b"
    min_chars: int = 40  # bu uzunluktan kısa metin parçaları LLM'e gönderilmez
    timeout: int = 60
    allow_remote: bool = False  # localhost dışındaki bir sunucuya yalnızca açık onayla bağlanılır


@dataclass
class Settings:
    enabled: dict[str, bool] = field(default_factory=lambda: {k.value: v for k, v in DEFAULT_ENABLED.items()})
    tc_checksum: bool = True
    name_aliases: bool = True  # "Yılmaz Bey" gibi tek başına geçen soyadını da yakala
    custom_terms: list[str] = field(default_factory=list)  # "terim | TÜR" satırları
    exclude_terms: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_HEADERS))
    code_format: str = "bracket"
    output_dir: str = ""  # boşsa girdinin klasörü
    output_suffix: str = "_anonim"
    clean_metadata: bool = True
    ner_enabled: bool = True  # Türkçe NER modeli pakette varsa kullanılır
    recent: list[dict] = field(default_factory=list)
    llm: LLMSettings = field(default_factory=LLMSettings)

    def is_enabled(self, et: EntityType) -> bool:
        return bool(self.enabled.get(et.value, DEFAULT_ENABLED[et]))

    def custom_entries(self) -> list[tuple[str, EntityType]]:
        out: list[tuple[str, EntityType]] = []
        for line in self.custom_terms:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                term, _, typ = line.rpartition("|")
                try:
                    et = EntityType.parse(typ.strip())
                except ValueError:
                    term, et = line, EntityType.OZEL
            else:
                term, et = line, EntityType.OZEL
            if term.strip():
                out.append((term.strip(), et))
        return out

    def exclude_entries(self) -> list[str]:
        return [t.strip() for t in self.exclude_terms if t.strip() and not t.strip().startswith("#")]

    # --- kalıcılık ---
    @classmethod
    def path(cls) -> Path:
        return app_support_dir() / "ayarlar.json"

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        if not p.exists():
            return cls()
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        s = cls()
        for k, v in data.items():
            if k == "llm" and isinstance(v, dict):
                s.llm = LLMSettings(**{kk: vv for kk, vv in v.items() if kk in LLMSettings.__dataclass_fields__})
            elif k == "enabled" and isinstance(v, dict):
                s.enabled.update(v)
            elif k in cls.__dataclass_fields__:
                setattr(s, k, v)
        return s

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self) -> None:
        self.path().write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    def add_recent(self, name: str, when: str, found: int) -> None:
        self.recent = ([{"name": name, "when": when, "found": found}] + self.recent)[:8]
