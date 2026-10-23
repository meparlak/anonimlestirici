"""Dosya biçimleri. Her biçim metin parçalarını çıkarır ve biçimi koruyarak geri yazar."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from ..textutil import fold
from ..types import EntityType, Segment

if TYPE_CHECKING:
    from ..settings import Settings


class SpanSource(Protocol):
    """Değiştirilecek aralıkları veren nesne (anonimleştirme ya da geri çevirme)."""

    def spans(self, text: str, segment: Segment | None = None) -> list: ...

    def apply(self, text: str, segment: Segment | None = None) -> str: ...


class UnsupportedFile(Exception):
    pass


class Document:
    extensions: tuple[str, ...] = ()

    def __init__(self, path: Path, settings: "Settings"):
        self.path = Path(path)
        self.name = self.path.name
        self.settings = settings
        self.warnings: list[str] = []
        self.save_warnings: list[str] = []
        self.segments: list[Segment] = self.read()

    def read(self) -> list[Segment]:
        raise NotImplementedError

    def save(self, out: Path, replacer: SpanSource) -> None:
        raise NotImplementedError

    # Excel/CSV başlıkları için
    def header_hint(self, header: str) -> EntityType | None:
        key = header_key(header)
        if not key:
            return None
        for h, typ in self.settings.headers.items():
            if header_key(h) == key:
                try:
                    return EntityType.parse(typ)
                except ValueError:
                    return None
        return None


def header_key(text: str) -> str:
    t = fold(str(text))
    t = re.sub(r"[^\w]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


SUPPORTED = (".xlsx", ".xlsm", ".csv", ".docx", ".pptx", ".txt", ".md")

OLD_FORMATS = {
    ".doc": "Eski Word biçimi desteklenmiyor. Dosyayı Word'de açıp \"Farklı Kaydet → .docx\" ile kaydedin.",
    ".xls": "Eski Excel biçimi desteklenmiyor. Dosyayı Excel'de açıp \"Farklı Kaydet → .xlsx\" ile kaydedin.",
    ".ppt": "Eski PowerPoint biçimi desteklenmiyor. Dosyayı \"Farklı Kaydet → .pptx\" ile kaydedin.",
    ".pdf": "PDF henüz desteklenmiyor. Metni Word'e aktarıp .docx olarak verebilirsiniz.",
}


def check_supported(path: Path) -> str | None:
    """Desteklenmiyorsa kullanıcıya gösterilecek mesajı döndürür."""
    ext = path.suffix.lower()
    if path.name.startswith("~$"):
        return "Bu, Office'in geçici kilit dosyası. Asıl dosyayı seçin."
    if ext in OLD_FORMATS:
        return OLD_FORMATS[ext]
    if ext not in SUPPORTED:
        return f"{ext or 'Uzantısız'} dosyalar desteklenmiyor. Desteklenenler: {', '.join(SUPPORTED)}"
    return None


def open_document(path: Path, settings: "Settings") -> Document:
    from .csvfile import CsvDocument
    from .ooxml import DocxDocument, PptxDocument, XlsxDocument
    from .text import TextDocument

    msg = check_supported(path)
    if msg:
        raise UnsupportedFile(msg)
    ext = path.suffix.lower()
    for cls in (XlsxDocument, DocxDocument, PptxDocument, CsvDocument, TextDocument):
        if ext in cls.extensions:
            return cls(path, settings)
    raise UnsupportedFile(f"{ext} desteklenmiyor")


__all__ = ["Document", "open_document", "UnsupportedFile", "check_supported", "SUPPORTED", "header_key"]
