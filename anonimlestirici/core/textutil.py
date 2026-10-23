"""Türkçe büyük/küçük harf ve eşleştirme yardımcıları."""

from __future__ import annotations

import re
import unicodedata

_UPPER_MAP = str.maketrans({"i": "İ", "ı": "I"})
_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı"})
_FOLD_MAP = str.maketrans(
    {"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u", "â": "a", "î": "i", "û": "u"}
)

UPPER = "A-ZÇĞİÖŞÜÂÎÛ"
LOWER = "a-zçğıöşüâîû"
WORD_CHARS = UPPER + LOWER + "0-9"


def tr_lower(text: str) -> str:
    return text.translate(_LOWER_MAP).lower()


def tr_upper(text: str) -> str:
    return text.translate(_UPPER_MAP).upper()


def tr_title(word: str) -> str:
    if not word:
        return word
    return tr_upper(word[0]) + tr_lower(word[1:])


def fold(text: str) -> str:
    """Karşılaştırma anahtarı: küçük harf, Türkçe harfler sadeleştirilmiş, boşluklar tek."""
    t = tr_lower(text).translate(_FOLD_MAP)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).strip()


def normalize_key(text: str) -> str:
    return re.sub(r"\s+", " ", tr_lower(text)).strip()


_CLASS = {
    "i": "[iİ]",
    "İ": "[iİ]",
    "ı": "[ıI]",
    "I": "[ıI]",
}


def ci_pattern(value: str) -> str:
    """Değer için Türkçe büyük/küçük harf duyarsız, boşluk esnek bir düzenli ifade üretir."""
    parts: list[str] = []
    for ch in value.strip():
        if ch.isspace():
            if not parts or parts[-1] != r"\s+":
                parts.append(r"\s+")
        elif ch in _CLASS:
            parts.append(_CLASS[ch])
        elif ch.isalpha():
            lo, up = tr_lower(ch), tr_upper(ch)
            parts.append(f"[{re.escape(lo)}{re.escape(up)}]" if lo != up else re.escape(ch))
        else:
            parts.append(re.escape(ch))
    return "".join(parts)


def bounded(pattern: str) -> str:
    """Kelimenin ortasında eşleşmeyi önleyen sınırlar ekler."""
    return rf"(?<![{WORD_CHARS}])(?:{pattern})(?![{WORD_CHARS}])"


def digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def snippet(text: str, start: int, end: int, width: int = 60) -> tuple[str, int, int]:
    """Bulgunun etrafından kısa bir bağlam keser; yeni başlangıç/bitişi döndürür."""
    a = max(0, start - width)
    b = min(len(text), end + width)
    prefix = "…" if a > 0 else ""
    suffix = "…" if b < len(text) else ""
    ctx = prefix + text[a:b].replace("\n", " ") + suffix
    return ctx, start - a + len(prefix), end - a + len(prefix)
