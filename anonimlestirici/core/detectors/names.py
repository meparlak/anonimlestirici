"""Türkçe ad soyad dedektörü: ad sözlüğü + unvan bağlamı + büyük harf kuralları."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources

from ..textutil import LOWER, UPPER, fold
from ..types import EntityType, Finding, Segment
from .base import Detector


def _load(name: str) -> set[str]:
    text = resources.files("anonimlestirici.data").joinpath(name).read_text(encoding="utf-8")
    return {fold(line) for line in text.splitlines() if line.strip() and not line.startswith("#")}


@lru_cache(maxsize=1)
def lexicon() -> dict[str, set[str]]:
    ambiguous = _load("belirsiz_adlar.txt")
    return {
        "first": _load("adlar.txt") | ambiguous,
        "ambiguous": ambiguous,
        "surname": _load("soyadlar.txt"),
        "city": _load("iller.txt"),
    }


TITLES_BEFORE = {
    fold(t)
    for t in [
        "Sayın", "Sn", "Sn.", "Dr", "Dr.", "Prof", "Prof.", "Doç", "Doç.", "Av", "Av.", "Uzm", "Uzm.",
        "Öğr", "Öğr.", "Gör", "Gör.", "Arş", "Arş.", "Müh", "Müh.", "Op", "Op.", "Bay", "Bayan",
        "Hemşire", "Mühendis", "Teknisyen", "Usta", "Sayin",
    ]
}
TITLES_AFTER = {fold(t) for t in ["Bey", "Beyi", "Hanım", "Hanımı", "Hoca", "Hocam", "Usta", "Efendi", "Abla", "Abi"]}

# Büyük harfle yazılsa da isim olmayan, cümle başında sık geçen kelimeler.
STOPWORDS = {
    fold(w)
    for w in [
        "Bu", "Şu", "O", "Bir", "Ve", "İle", "Ama", "Ancak", "Fakat", "Ayrıca", "Bugün", "Dün", "Yarın",
        "Toplantı", "Konu", "Tarih", "Saat", "Not", "Ek", "Ekte", "Sonuç", "Karar", "Madde", "Bölüm",
        "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim",
        "Kasım", "Aralık", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar",
        "Türkiye", "Müdür", "Müdürü", "Başkan", "Başkanı", "Sorumlu", "Sorumlusu", "Şef", "Şefi",
        "Personel", "Müşteri", "Firma", "Kurum", "Birim", "Kalite", "Üretim", "Satış", "Satın", "Bilgi",
        "Genel", "Teknik", "İnsan", "Kaynakları", "Hat", "Hattı", "Vardiya", "Ürün", "Parça", "Sipariş",
        "Şikayet", "Şikâyet", "Uygunsuzluk", "Düzeltici", "Önleyici", "Faaliyet", "Rapor", "Denetim",
        "Merkez", "Merkezi", "Daire", "Şube", "Mah", "Mahallesi", "Cad", "Caddesi", "Sok", "Sokak",
        "No", "Kat", "Blok",
    ]
}

# Ad/soyad kelimesinin peşinden gelip ismi bitiren kurum/birim sözcükleri.
ORG_WORDS = {
    fold(w)
    for w in [
        "Üniversitesi", "Fakültesi", "Müdürlüğü", "Başkanlığı", "Birimi", "Bölümü", "Belediyesi", "Hastanesi",
        "Lisesi", "Okulu", "Vakfı", "Derneği", "Makine", "Makina", "İnşaat", "Ticaret", "Sanayi", "Holding",
        "Grup", "Grubu", "Otomotiv", "Tekstil", "Gıda", "Lojistik", "Enerji", "Yazılım", "Bilişim",
        "Caddesi", "Cad", "Sokak", "Sok", "Mahallesi", "Mah", "Bulvarı", "Apartmanı", "Sitesi", "Camii",
        "Parkı", "Kampüsü", "Yerleşkesi", "Ltd", "A.Ş", "AŞ",
    ]
}

_TOKEN = re.compile(
    rf"[{UPPER}](?:[{LOWER}]+|[{UPPER}]+)(?:-[{UPPER}][{LOWER}{UPPER}]+)?\.?|[{UPPER}]\.|[{LOWER}]+\.?|\S"
)


class NameDetector(Detector):
    name = "Ad sözlüğü"
    types = (EntityType.KISI,)

    def detect(self, segment: Segment) -> list[Finding]:
        if not self.settings.is_enabled(EntityType.KISI):
            return []
        lex = lexicon()
        text = segment.text
        tokens = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(text)]
        out: list[Finding] = []
        i = 0
        n = len(tokens)

        def word(k: int) -> str:
            return tokens[k][2].rstrip(".") if 0 <= k < n else ""

        def adjacent(k: int) -> bool:
            """tokens[k] ile tokens[k+1] arasında yalnızca tek bir boşluk/satır içi boşluk mu var?"""
            if k + 1 >= n:
                return False
            gap = text[tokens[k][1] : tokens[k + 1][0]]
            return gap in (" ", " ", "  ")

        def ends(k: int) -> bool:
            """Kelime cümleyi bitiriyor mu? ("Doğan." evet, "A." baş harf olduğu için hayır)"""
            t = tokens[k][2]
            return t.endswith(".") and len(t) > 2

        def is_cap(k: int) -> bool:
            w = word(k)
            return bool(w) and w[0].isupper() and len(w) >= 2 and w[1:].replace("-", "").isalpha()

        def is_first(k: int) -> bool:
            return is_cap(k) and fold(word(k)) in lex["first"]

        while i < n:
            if not is_first(i) or fold(word(i)) in STOPWORDS:
                # "A. Yılmaz" veya "Sayın Yılmaz" gibi soyadıyla başlayan kalıplar
                f = self._initial_or_title(text, tokens, i, lex)
                if f:
                    out.append(f)
                    while i < n and tokens[i][1] <= f.end:
                        i += 1
                    continue
                i += 1
                continue

            start_k = i
            j = i
            # Birden fazla ad: "Mehmet Enes", "Ayşe Nur"
            while not ends(j) and adjacent(j) and is_first(j + 1) and fold(word(j + 1)) not in ORG_WORDS:
                # Son ad aynı zamanda soyadı olabilir ("Ali Yılmaz"); yine de ad dizisine dahil et.
                j += 1
            names_end = j
            # Soyadı: ad dizisinden sonra gelen büyük harfli kelime(ler)
            surname_k = []
            k = j
            while not ends(k) and adjacent(k) and is_cap(k + 1) and len(surname_k) < 2:
                w = fold(word(k + 1))
                if w in STOPWORDS or w in ORG_WORDS or w in TITLES_AFTER:
                    break
                if surname_k and w not in lex["surname"]:
                    break
                surname_k.append(k + 1)
                k += 1
            # Peşinden kurum sözcüğü geliyorsa ("Yılmaz Makine") bu bir kurum adının parçası olabilir
            follow = fold(word(k + 1)) if adjacent(k) and not ends(k) else ""
            org_follows = follow in ORG_WORDS

            first_word = fold(word(start_k))
            title_before = start_k > 0 and fold(word(start_k - 1)) in TITLES_BEFORE
            title_after = adjacent(k) and not ends(k) and fold(word(k + 1)) in TITLES_AFTER
            ambiguous = first_word in lex["ambiguous"] and names_end == start_k

            if surname_k:
                last_sur = fold(word(surname_k[-1]))
                if ambiguous:
                    conf = 0.85 if (last_sur in lex["surname"] or title_before or title_after) else 0.4
                else:
                    conf = 0.9 if last_sur in lex["surname"] else 0.8
                end_k = surname_k[-1]
            elif names_end > start_k:
                conf = 0.75  # "Ayşe Nur" gibi iki ad, soyadı yok
                end_k = names_end
            else:
                end_k = start_k
                if title_before or title_after:
                    conf = 0.75
                elif ambiguous:
                    conf = 0.2
                else:
                    conf = 0.55
            if org_follows:
                conf = min(conf, 0.35)

            s = tokens[start_k][0]
            e = tokens[end_k][1]
            frag = text[s:e].rstrip(".")
            e = s + len(frag)
            out.append(Finding(s, e, frag, EntityType.KISI, conf, self.name))
            i = end_k + 1
        return out

    def _initial_or_title(self, text, tokens, i, lex) -> Finding | None:
        n = len(tokens)
        tok = tokens[i][2]
        # "A. Yılmaz"
        if re.fullmatch(rf"[{UPPER}]\.", tok) and i + 1 < n:
            nxt = tokens[i + 1][2].rstrip(".")
            if fold(nxt) in lex["surname"] and text[tokens[i][1] : tokens[i + 1][0]] in (" ", ""):
                s, e = tokens[i][0], tokens[i + 1][0] + len(nxt)
                return Finding(s, e, text[s:e], EntityType.KISI, 0.7, self.name)
        # Sözlükte olmayan ad + bilinen soyadı: "Oya Tekin"
        word = tok.rstrip(".")
        if (
            i + 1 < n
            and not tok.endswith(".")
            and len(word) >= 2
            and word[0].isupper()
            and word[1:].isalpha()
            and text[tokens[i][1] : tokens[i + 1][0]] == " "
            and fold(word) not in STOPWORDS
            and fold(word) not in ORG_WORDS
            and fold(word) not in TITLES_BEFORE
            and fold(word) not in TITLES_AFTER
            and fold(word) not in lex["city"]
        ):
            nxt = tokens[i + 1][2].rstrip(".")
            if nxt[:1].isupper() and fold(nxt) in lex["surname"]:
                s = tokens[i][0]
                e = tokens[i + 1][0] + len(nxt)
                return Finding(s, e, text[s:e], EntityType.KISI, 0.55, self.name)
        # "Sayın Yılmaz", "Dr. Kaya"
        if fold(tok.rstrip(".")) in TITLES_BEFORE or fold(tok) in TITLES_BEFORE:
            if i + 1 < n:
                nxt = tokens[i + 1][2].rstrip(".")
                if nxt[:1].isupper() and fold(nxt) in lex["surname"] and fold(nxt) not in lex["first"]:
                    s = tokens[i + 1][0]
                    return Finding(s, s + len(nxt), nxt, EntityType.KISI, 0.7, self.name)
        return None


def name_parts(value: str) -> tuple[str, str] | None:
    """'Ahmet Yılmaz' → ('Ahmet', 'Yılmaz'). Tek kelimelik değerler için None."""
    words = [w for w in re.split(r"\s+", value.strip()) if w]
    if len(words) < 2:
        return None
    return words[0], words[-1]
