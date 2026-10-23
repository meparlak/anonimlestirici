"""Biçimi belli veriler için kalıp (düzenli ifade) dedektörleri."""

from __future__ import annotations

import re

from ..textutil import WORD_CHARS, digits, fold
from ..types import EntityType, Finding, Segment
from .base import Detector


def tc_valid(num: str) -> bool:
    if len(num) != 11 or not num.isdigit() or num[0] == "0":
        return False
    d = [int(c) for c in num]
    d10 = ((d[0] + d[2] + d[4] + d[6] + d[8]) * 7 - (d[1] + d[3] + d[5] + d[7])) % 10
    d11 = sum(d[:10]) % 10
    return d[9] == d10 and d[10] == d11


def vkn_valid(num: str) -> bool:
    """Vergi kimlik numarası (10 hane) doğrulama algoritması."""
    if len(num) != 10 or not num.isdigit():
        return False
    total = 0
    for i in range(9):
        t = (int(num[i]) + 9 - i) % 10
        v = (t * 2 ** (9 - i)) % 9
        if t != 0 and v == 0:
            v = 9
        total += v
    return (10 - total % 10) % 10 == int(num[9])


def luhn_valid(num: str) -> bool:
    d = [int(c) for c in num if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    total = 0
    for i, x in enumerate(reversed(d)):
        if i % 2:
            x *= 2
            if x > 9:
                x -= 9
        total += x
    return total % 10 == 0


def iban_valid(iban: str) -> bool:
    s = re.sub(r"\s", "", iban).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]+", s):
        return False
    rearranged = s[4:] + s[:4]
    num = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(num) % 97 == 1


_TC = re.compile(r"(?<!\d)([1-9]\d{10})(?!\d)")
_TC_CONTEXT = re.compile(r"(t\.?\s?c\.?|tckn|kimlik)", re.I)

_PHONE = re.compile(
    r"(?<![\d+])"
    r"(?P<prefix>(?:\+|00)\s?90[\s.-]?|\(?0[\s.-]?)?"
    r"(?P<area>\(?[2-58]\d{2}\)?)"
    r"(?P<s1>[\s.-]?)(?P<a>\d{3})(?P<s2>[\s.-]?)(?P<b>\d{2})(?P<s3>[\s.-]?)(?P<c>\d{2})"
    r"(?!\d)"
)

_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")

_IBAN = re.compile(r"(?<![A-Za-z0-9])TR\s?\d{2}(?:\s?[0-9A-Z]{4}){5}\s?[0-9A-Z]{2}(?![A-Za-z0-9])", re.I)

_PLATE = re.compile(
    rf"(?<![{WORD_CHARS}])(0[1-9]|[1-7]\d|8[01])\s?([A-PR-VYZ]{{1,3}})\s?(\d{{2,5}})(?![{WORD_CHARS}])"
)

_CARD = re.compile(r"(?<![\d-])(?:\d{4}[ -]?){3}\d{1,7}(?![\d-])")
_CARD_CONTEXT = re.compile(r"kart|card|visa|master", re.I)
_VKN = re.compile(r"(?<!\d)\d{10}(?!\d)")
_VKN_CONTEXT = re.compile(r"vergi|vkn|v\.?\s?d\.?|v\.?\s?n\.?", re.I)

_IP = re.compile(r"(?<![\d.])(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)(?![\d.])")

_DATE = re.compile(
    r"(?<!\d)(?:(?:0?[1-9]|[12]\d|3[01])[./-](?:0?[1-9]|1[0-2])[./-](?:19|20)\d{2}"
    r"|(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01]))(?!\d)"
)


class PatternDetector(Detector):
    name = "Kalıp"
    types = (
        EntityType.TC,
        EntityType.TELEFON,
        EntityType.EPOSTA,
        EntityType.IBAN,
        EntityType.PLAKA,
        EntityType.TARIH,
        EntityType.IP,
        EntityType.FINANS,
        EntityType.VERGI,
    )

    def detect(self, segment: Segment) -> list[Finding]:
        text = segment.text
        out: list[Finding | None] = []

        for m in _EMAIL.finditer(text):
            out.append(self.finding(m.start(), m.end(), m.group(), EntityType.EPOSTA, 0.98))

        for m in _IBAN.finditer(text):
            conf = 0.97 if iban_valid(m.group()) else 0.7
            out.append(self.finding(m.start(), m.end(), m.group(), EntityType.IBAN, conf))

        tc_spans = []
        for m in _TC.finditer(text):
            num = m.group(1)
            before = text[max(0, m.start() - 25) : m.start()]
            if tc_valid(num):
                conf = 0.97
            elif segment.hint == EntityType.TC or _TC_CONTEXT.search(before) or not self.settings.tc_checksum:
                conf = 0.75
            else:
                continue
            tc_spans.append((m.start(), m.end()))
            out.append(self.finding(m.start(), m.end(), num, EntityType.TC, conf))

        for m in _PHONE.finditer(text):
            if any(a <= m.start() < b for a, b in tc_spans):
                continue
            prefix = m.group("prefix") or ""
            area = m.group("area").strip("()")
            seps = (m.group("s1") or "") + (m.group("s2") or "") + (m.group("s3") or "")
            # Önek ya da ayırıcı yoksa yalnızca 5xx (cep) numaralarını kabul et; diğer 10 haneli sayılar
            # sipariş/seri numarası olabilir.
            if not prefix and not seps and not area.startswith("5") and segment.hint != EntityType.TELEFON:
                continue
            if not prefix and not area.startswith("5") and "(" not in m.group("area") and segment.hint != EntityType.TELEFON:
                # "264 295 10 10" gibi öneksiz sabit hat: yalnızca bağlamda telefon geçiyorsa
                before = fold(text[max(0, m.start() - 20) : m.start()])
                if not re.search(r"tel|gsm|ara|iletisim|faks|fax", before):
                    continue
            conf = 0.95 if prefix or area.startswith("5") else 0.8
            out.append(self.finding(m.start(), m.end(), m.group(), EntityType.TELEFON, conf))

        for m in _PLATE.finditer(text):
            letters, nums = m.group(2), m.group(3)
            ok = (len(letters) == 1 and 4 <= len(nums) <= 5) or (len(letters) == 2 and 3 <= len(nums) <= 4) or (
                len(letters) == 3 and 2 <= len(nums) <= 3
            )
            if ok:
                out.append(self.finding(m.start(), m.end(), m.group(), EntityType.PLAKA, 0.8))

        for m in _CARD.finditer(text):
            before = text[max(0, m.start() - 25) : m.start()]
            if luhn_valid(m.group()):
                out.append(self.finding(m.start(), m.end(), m.group(), EntityType.FINANS, 0.9))
            elif _CARD_CONTEXT.search(before):
                out.append(self.finding(m.start(), m.end(), m.group(), EntityType.FINANS, 0.75))

        for m in _VKN.finditer(text):
            before = text[max(0, m.start() - 25) : m.start()]
            if _VKN_CONTEXT.search(before) or (vkn_valid(m.group()) and segment.hint == EntityType.VERGI):
                out.append(self.finding(m.start(), m.end(), m.group(), EntityType.VERGI, 0.85))

        for m in _IP.finditer(text):
            out.append(self.finding(m.start(), m.end(), m.group(), EntityType.IP, 0.9))

        for m in _DATE.finditer(text):
            out.append(self.finding(m.start(), m.end(), m.group(), EntityType.TARIH, 0.9))

        return [f for f in out if f]


def canonical_key(et: EntityType, text: str) -> str:
    """Aynı değerin farklı yazımlarını (0532 123 45 67 / 05321234567) aynı anahtara indirger."""
    from ..textutil import normalize_key

    if et == EntityType.TELEFON:
        return digits(text)[-10:]
    if et in (EntityType.TC,):
        return digits(text)
    if et == EntityType.IBAN:
        return re.sub(r"\s", "", text).upper()
    if et == EntityType.EPOSTA:
        return text.strip().lower()
    if et in (EntityType.VERGI, EntityType.FINANS, EntityType.BELGE):
        return re.sub(r"[\s-]", "", text).upper()
    if et == EntityType.PLAKA:
        return re.sub(r"\s", "", text).upper()
    return normalize_key(text.strip(" .,;:"))
