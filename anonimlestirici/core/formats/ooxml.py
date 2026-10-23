"""Office Open XML (.docx, .pptx, .xlsx) dosyaları.

Dosya bir zip arşividir. Yalnızca metin içeren XML parçaları değiştirilir; diğer bütün
parçalar (resimler, grafikler, stiller, makrolar) bayt bayt aynen kopyalanır. Böylece
biçimlendirme, grafikler ve pivot tablolar korunur.

Bir isim Word'de birden fazla biçim parçasına (run) bölünmüş olabilir ("Ah" + "met").
Paragraf metni birleştirilip taranır, değişiklik parçalara biçimi bozmadan dağıtılır.
"""

from __future__ import annotations

import fnmatch
import re
import zipfile
from pathlib import Path
from typing import Callable

from lxml import etree

from ..types import EntityType, Segment
from . import Document

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "cp": "http://schemas.openxmlformats.org/package/2006/metadata/core-properties",
    "dc": "http://purl.org/dc/elements/1.1/",
    "ep": "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties",
    "w15": "http://schemas.microsoft.com/office/word/2012/wordml",
    "xtc": "http://schemas.microsoft.com/office/spreadsheetml/2018/threadedcomments",
    "p188": "http://schemas.microsoft.com/office/powerpoint/2018/8/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
}
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"


def q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


# ---------------------------------------------------------------- birimler


class Unit:
    """Geri yazılabilen tek bir metin birimi."""

    part: str

    def text(self) -> str:
        raise NotImplementedError

    def write(self, replacer, segment: Segment) -> bool:
        raise NotImplementedError


class NodesUnit(Unit):
    """Birden fazla metin düğümünden oluşan paragraf (w:t, a:t, x:t)."""

    def __init__(self, part: str, nodes: list, preserve_space: bool = True):
        self.part = part
        self.nodes = nodes
        self.preserve_space = preserve_space

    def text(self) -> str:
        return "".join(n.text or "" for n in self.nodes)

    def write(self, replacer, segment) -> bool:
        full = self.text()
        spans = replacer.spans(full, segment)
        if not spans:
            return False
        texts = [n.text or "" for n in self.nodes]
        starts = []
        pos = 0
        for t in texts:
            starts.append(pos)
            pos += len(t)

        def locate(offset: int, is_end: bool) -> int:
            for i, (st, t) in enumerate(zip(starts, texts)):
                if not t:
                    continue
                if (st <= offset < st + len(t)) or (is_end and st < offset <= st + len(t)):
                    return i
            return len(texts) - 1

        orig = list(texts)
        for sp in sorted(spans, key=lambda s: s.start, reverse=True):
            a = locate(sp.start, False)
            b = locate(sp.end, True)
            sa = sp.start - starts[a]
            eb = sp.end - starts[b]
            if a == b:
                texts[a] = texts[a][:sa] + sp.replacement + texts[a][eb:]
            else:
                texts[a] = texts[a][:sa] + sp.replacement
                for k in range(a + 1, b):
                    texts[k] = ""
                texts[b] = texts[b][eb:]
        for n, new, old in zip(self.nodes, texts, orig):
            if new != old:
                n.text = new
                if self.preserve_space:
                    n.set(XML_SPACE, "preserve")
        return True


class TextUnit(Unit):
    """Tek bir öğenin metni (dc:creator, p:text...)."""

    def __init__(self, part: str, el):
        self.part = part
        self.el = el

    def text(self) -> str:
        return self.el.text or ""

    def write(self, replacer, segment) -> bool:
        new = replacer.apply(self.text(), segment)
        if new != self.text():
            self.el.text = new
            return True
        return False


class AttrUnit(Unit):
    def __init__(self, part: str, el, attr: str, transform: Callable[[str], str] | None = None):
        self.part = part
        self.el = el
        self.attr = attr
        self.transform = transform

    def text(self) -> str:
        return self.el.get(self.attr) or ""

    def write(self, replacer, segment) -> bool:
        old = self.text()
        new = replacer.apply(old, segment)
        if self.transform and new != old:
            new = self.transform(new)
        if new != old:
            self.el.set(self.attr, new)
            return True
        return False


# ---------------------------------------------------------------- temel sınıf


class OOXMLDocument(Document):
    def read(self) -> list[Segment]:
        try:
            self.zf = zipfile.ZipFile(self.path)
        except zipfile.BadZipFile as e:
            raise ValueError(
                "Dosya açılamadı. Parola korumalı ya da bozuk olabilir. Parolasını kaldırıp yeniden deneyin."
            ) from e
        self.infos = self.zf.infolist()
        self.names = [i.filename for i in self.infos]
        self.trees: dict[str, etree._ElementTree] = {}
        self.units: list[tuple[Unit, Segment]] = []
        self._ordered: list[Segment] = []  # taranacak parçalar, belgedeki sırasıyla
        self.collect()
        self.check_media()
        return self._ordered

    def tree(self, name: str):
        if name not in self.trees:
            parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, huge_tree=True)
            self.trees[name] = etree.fromstring(self.zf.read(name), parser).getroottree()
        return self.trees[name]

    def parts(self, *patterns: str) -> list[str]:
        out = []
        for n in self.names:
            if any(fnmatch.fnmatch(n, p) for p in patterns) and n not in out:
                out.append(n)
        return sorted(out, key=_natural)

    def add(self, unit: Unit, location: str, hint: EntityType | None = None, whole: bool = False,
            write_only: bool = False) -> None:
        seg = Segment(unit.text(), location, hint=hint, whole=whole)
        self.units.append((unit, seg))
        if not write_only:
            self._ordered.append(seg)

    def count_only(self, seg: Segment) -> None:
        """Yalnızca taranıp sayılan parça (xlsx'te paylaşılan metni kullanan hücre)."""
        self._ordered.append(seg)

    def collect(self) -> None:
        raise NotImplementedError

    def check_media(self) -> None:
        if any(n.startswith(("word/media/", "ppt/media/", "xl/media/")) for n in self.names):
            self.warnings.append(
                "Belgede resim var. Resimlerin içindeki yazılar (taranmış belge, ekran görüntüsü) anonimleştirilmez."
            )

    # --- ortak toplayıcılar

    def collect_paragraphs(self, part: str, label: str, para_tag: str, text_tag: str, preserve: bool = True) -> None:
        root = self.tree(part).getroot()
        n = 0
        for p in root.iter(para_tag):
            nodes = [t for t in p.iter(text_tag) if _nearest(t, para_tag) is p]
            if not nodes:
                continue
            n += 1
            unit = NodesUnit(part, nodes, preserve)
            if unit.text().strip():
                self.add(unit, f"{label} ¶{n}")

    def collect_core_props(self) -> None:
        if "docProps/core.xml" in self.names and self.settings.clean_metadata:
            root = self.tree("docProps/core.xml").getroot()
            for tag, label in ((q("dc", "creator"), "yazar"), (q("cp", "lastModifiedBy"), "son değiştiren")):
                for el in root.iter(tag):
                    if (el.text or "").strip():
                        self.add(TextUnit("docProps/core.xml", el), f"Belge bilgisi: {label}", EntityType.KISI, True)
            for tag in (q("dc", "title"), q("dc", "subject"), q("dc", "description"), q("cp", "keywords")):
                for el in root.iter(tag):
                    if (el.text or "").strip():
                        self.add(TextUnit("docProps/core.xml", el), "Belge bilgisi: başlık/konu")
        if "docProps/app.xml" in self.names and self.settings.clean_metadata:
            root = self.tree("docProps/app.xml").getroot()
            for tag, et, label in ((q("ep", "Company"), EntityType.KURUM, "şirket"), (q("ep", "Manager"), EntityType.KISI, "yönetici")):
                for el in root.iter(tag):
                    if (el.text or "").strip():
                        self.add(TextUnit("docProps/app.xml", el), f"Belge bilgisi: {label}", et, True)

    def collect_external_links(self, pattern: str) -> None:
        for part in self.parts(pattern):
            root = self.tree(part).getroot()
            for rel in root.iter(q("rel", "Relationship")):
                if rel.get("TargetMode") == "External" and rel.get("Target"):
                    self.add(AttrUnit(part, rel, "Target"), "Bağlantı adresi")

    def collect_charts(self, pattern: str) -> None:
        """Grafik başlıkları ve grafiğin içinde saklanan hücre değerleri (önbellek)."""
        for part in self.parts(pattern):
            self.collect_paragraphs(part, "Grafik", q("a", "p"), q("a", "t"), preserve=False)
            root = self.tree(part).getroot()
            for cache in root.iter(q("c", "strCache")):
                for v in cache.iter(q("c", "v")):
                    if (v.text or "").strip():
                        self.add(TextUnit(part, v), "Grafik verisi", whole=True)

    def collect_attr(self, part: str, tag: str, attr: str, label: str, hint: EntityType | None = EntityType.KISI) -> None:
        root = self.tree(part).getroot()
        for el in root.iter(tag):
            if el.get(attr):
                self.add(AttrUnit(part, el, attr), label, hint, True)

    # --- yazma

    def save(self, out: Path, replacer) -> None:
        changed: set[str] = set()
        for unit, seg in self.units:
            if unit.write(replacer, seg):
                changed.add(unit.part)
        changed |= self.after_write(replacer)
        with zipfile.ZipFile(out, "w") as zout:
            for info in self.infos:
                if info.filename in changed:
                    data = etree.tostring(self.trees[info.filename], xml_declaration=True, encoding="UTF-8", standalone=True)
                else:
                    data = self.zf.read(info.filename)
                zout.writestr(info, data, compress_type=info.compress_type)

    def after_write(self, replacer) -> set[str]:
        return set()


def _nearest(el, tag):
    p = el.getparent()
    while p is not None and p.tag != tag:
        p = p.getparent()
    return p


def _natural(s: str):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", s)]


# ---------------------------------------------------------------- Word


class DocxDocument(OOXMLDocument):
    extensions = (".docx", ".docm")

    def collect(self) -> None:
        W_P, W_T = q("w", "p"), q("w", "t")
        labels = [
            ("word/document.xml", "Gövde"),
            ("word/header*.xml", "Üst bilgi"),
            ("word/footer*.xml", "Alt bilgi"),
            ("word/footnotes.xml", "Dipnot"),
            ("word/endnotes.xml", "Son not"),
            ("word/comments.xml", "Yorum"),
        ]
        for pattern, label in labels:
            for part in self.parts(pattern):
                self.collect_paragraphs(part, label, W_P, W_T)
                root = self.tree(part).getroot()
                # Değişiklik izlemede silinmiş metin ve alan kodları (ör. HYPERLINK "mailto:...")
                for tag, lab in ((q("w", "delText"), "silinmiş metin"), (q("w", "instrText"), "alan kodu")):
                    for el in root.iter(tag):
                        if (el.text or "").strip():
                            self.add(TextUnit(part, el), f"{label}: {lab}")
                if self.settings.clean_metadata:
                    for el in root.iter():
                        if el.get(q("w", "author")):
                            self.add(AttrUnit(part, el, q("w", "author")), f"{label}: değişiklik/yorum yazarı",
                                     EntityType.KISI, True)
                    for el in root.iter(q("w", "comment")):
                        if el.get(q("w", "initials")):
                            el.set(q("w", "initials"), "")
                            self.trees_dirty = True
        self.collect_charts("word/charts/chart*.xml")
        # SmartArt metinleri
        for part in self.parts("word/diagrams/data*.xml", "word/diagrams/drawing*.xml"):
            self.collect_paragraphs(part, "Diyagram", q("a", "p"), q("a", "t"), preserve=False)
        if "word/people.xml" in self.names and self.settings.clean_metadata:
            self.collect_attr("word/people.xml", q("w15", "person"), q("w15", "author"), "Yorum yazarı")
        self.collect_external_links("word/_rels/*.rels")
        self.collect_core_props()

    def after_write(self, replacer) -> set[str]:
        # yorum baş harfleri okuma sırasında temizlendi
        if getattr(self, "trees_dirty", False):
            return {"word/comments.xml"} & set(self.trees)
        return set()


# ---------------------------------------------------------------- PowerPoint


class PptxDocument(OOXMLDocument):
    extensions = (".pptx", ".pptm")

    def collect(self) -> None:
        A_P, A_T = q("a", "p"), q("a", "t")
        for pattern, label in (
            ("ppt/slides/slide*.xml", "Slayt"),
            ("ppt/notesSlides/notesSlide*.xml", "Konuşmacı notu"),
            ("ppt/slideMasters/slideMaster*.xml", "Asıl slayt"),
            ("ppt/slideLayouts/slideLayout*.xml", "Slayt düzeni"),
            ("ppt/diagrams/data*.xml", "Diyagram"),
            ("ppt/diagrams/drawing*.xml", "Diyagram"),
            ("ppt/comments/modernComment*.xml", "Yorum"),
        ):
            for part in self.parts(pattern):
                num = re.findall(r"(\d+)\.xml$", part)
                self.collect_paragraphs(part, f"{label} {num[0] if num else ''}".strip(), A_P, A_T, preserve=False)
        self.collect_charts("ppt/charts/chart*.xml")
        for part in self.parts("ppt/comments/comment*.xml"):
            root = self.tree(part).getroot()
            for el in root.iter(q("p", "text")):
                if (el.text or "").strip():
                    self.add(TextUnit(part, el), "Yorum")
        if self.settings.clean_metadata:
            if "ppt/commentAuthors.xml" in self.names:
                self.collect_attr("ppt/commentAuthors.xml", q("p", "cmAuthor"), "name", "Yorum yazarı")
                self._clear_initials("ppt/commentAuthors.xml", q("p", "cmAuthor"))
            if "ppt/authors.xml" in self.names:
                self.collect_attr("ppt/authors.xml", q("p188", "author"), "name", "Yorum yazarı")
                self._clear_initials("ppt/authors.xml", q("p188", "author"))
        self.collect_external_links("ppt/slides/_rels/*.rels")
        self.collect_core_props()

    def _clear_initials(self, part, tag):
        for el in self.tree(part).getroot().iter(tag):
            if el.get("initials"):
                el.set("initials", "")
                self._dirty = getattr(self, "_dirty", set()) | {part}

    def after_write(self, replacer) -> set[str]:
        return getattr(self, "_dirty", set())


# ---------------------------------------------------------------- Excel

_CELL_REF = re.compile(r"([A-Z]+)(\d+)")
_SHEET_BAD = re.compile(r"[\[\]:*?/\\]")


class NumberCellUnit(Unit):
    """Sayı olarak saklanmış TC/telefon. Değişirse hücre metne çevrilir."""

    def __init__(self, part, cell):
        self.part = part
        self.cell = cell
        self.v = cell.find(q("x", "v"))

    def text(self) -> str:
        return self.v.text or ""

    def write(self, replacer, segment) -> bool:
        new = replacer.apply(self.text(), segment)
        if new == self.text():
            return False
        self.cell.remove(self.v)
        self.cell.set("t", "inlineStr")
        is_ = etree.SubElement(self.cell, q("x", "is"))
        t = etree.SubElement(is_, q("x", "t"))
        t.text = new
        t.set(XML_SPACE, "preserve")
        return True


class XlsxDocument(OOXMLDocument):
    extensions = (".xlsx", ".xlsm")

    def collect(self) -> None:
        X = lambda local: q("x", local)  # noqa: E731
        self.sheet_names = self._sheet_map()

        # Paylaşılan metinler: her biri bir kez yazılır, hücrelerde sayılır.
        shared: list[str] = []
        if "xl/sharedStrings.xml" in self.names:
            root = self.tree("xl/sharedStrings.xml").getroot()
            for i, si in enumerate(root.iterchildren(X("si"))):
                nodes = [t for t in si.iter(X("t")) if _nearest(t, X("rPh")) is None]
                unit = NodesUnit("xl/sharedStrings.xml", nodes)
                shared.append(unit.text())
                if nodes:
                    self.add(unit, f"Paylaşılan metin {i + 1}", write_only=True)

        for part, title in self.sheet_names.items():
            root = self.tree(part).getroot()
            rows = list(root.iter(X("row")))
            cells: list[tuple[str, int, object, str, str]] = []  # (sütun, satır, eleman, tür, metin)
            for row in rows:
                for c in row.iterchildren(X("c")):
                    ref = c.get("r") or ""
                    m = _CELL_REF.match(ref)
                    if not m:
                        continue
                    col, rnum = m.group(1), int(m.group(2))
                    t = c.get("t")
                    if c.find(X("f")) is not None:
                        continue  # formül hücresi
                    if t == "s":
                        v = c.find(X("v"))
                        try:
                            txt = shared[int(v.text)]
                        except (TypeError, ValueError, IndexError, AttributeError):
                            continue
                        cells.append((col, rnum, c, "s", txt))
                    elif t == "inlineStr":
                        nodes = list(c.iter(X("t")))
                        if nodes:
                            cells.append((col, rnum, NodesUnit(part, nodes), "inline", "".join(n.text or "" for n in nodes)))
                    elif t in (None, "n"):
                        v = c.find(X("v"))
                        if v is not None and v.text and re.fullmatch(r"\d{10,11}(?:\.0)?", v.text):
                            cells.append((col, rnum, NumberCellUnit(part, c), "num", v.text.split(".")[0]))
                    elif t == "str":
                        pass  # formül sonucu
            hints = self._header_hints(cells)
            header_row = hints.pop("_row", None)
            for col, rnum, obj, kind, txt in cells:
                hint = hints.get(col) if header_row is not None and rnum > header_row else None
                loc = f"{title}!{col}{rnum}"
                if kind == "s":
                    self.count_only(Segment(txt, loc, hint=hint, whole=True))
                else:
                    self.add(obj, loc, hint=hint, whole=True)

        # Yorumlar
        for part in self.parts("xl/comments*.xml"):
            root = self.tree(part).getroot()
            for cm in root.iter(X("comment")):
                text_el = cm.find(X("text"))
                if text_el is None:
                    continue
                nodes = list(text_el.iter(X("t")))
                if nodes:
                    self.add(NodesUnit(part, nodes), f"Yorum {cm.get('ref', '')}")
            if self.settings.clean_metadata:
                for au in root.iter(X("author")):
                    if (au.text or "").strip():
                        self.add(TextUnit(part, au), "Yorum yazarı", EntityType.KISI, True)
        for part in self.parts("xl/threadedComments/*.xml"):
            root = self.tree(part).getroot()
            for el in root.iter(q("xtc", "text")):
                if (el.text or "").strip():
                    self.add(TextUnit(part, el), "Yorum")
        if self.settings.clean_metadata:
            for part in self.parts("xl/persons/*.xml"):
                self.collect_attr(part, q("xtc", "person"), "displayName", "Yorum yazarı")

        # Sayfa adları ("Ahmet Yılmaz" adlı sayfa)
        wb = self.tree("xl/workbook.xml").getroot()
        for sh in wb.iter(X("sheet")):
            self.add(AttrUnit("xl/workbook.xml", sh, "name", transform=_safe_sheet_name), "Sayfa adı")
        self.collect_external_links("xl/worksheets/_rels/*.rels")
        self.collect_core_props()

        self.collect_charts("xl/charts/chart*.xml")
        # Pivot önbelleği hücre değerlerinin bir kopyasını tutar
        for part in self.parts("xl/pivotCache/pivotCache*.xml"):
            root = self.tree(part).getroot()
            for el in root.iter(X("s")):
                if el.get("v", "").strip():
                    self.add(AttrUnit(part, el, "v"), "Pivot önbelleği", write_only=True)
        if self.parts("xl/pivotCache/pivotCache*.xml"):
            self.warnings.append(
                "Dosyada pivot tablo var. Pivot önbelleğindeki değerler de anonimleştirilir; Excel'de \"Yenile\" "
                "deyince pivot tablo anonim verilerle yeniden hesaplanır."
            )

    def _sheet_map(self) -> dict[str, str]:
        wb = self.tree("xl/workbook.xml").getroot()
        rels = self.tree("xl/_rels/workbook.xml.rels").getroot()
        targets = {r.get("Id"): r.get("Target") for r in rels.iter(q("rel", "Relationship"))}
        out = {}
        for sh in wb.iter(q("x", "sheet")):
            rid = sh.get(q("r", "id"))
            target = targets.get(rid, "")
            if not target:
                continue
            path = target.lstrip("/") if target.startswith("/") else "xl/" + target
            path = re.sub(r"[^/]+/\.\./", "", path)
            if path in self.names:
                out[path] = sh.get("name")
        return out

    def _header_hints(self, cells) -> dict:
        """İlk 10 satırda başlık satırını bulur: {sütun: tür, '_row': satır}."""
        by_row: dict[int, list] = {}
        for col, rnum, _, kind, txt in cells:
            if rnum <= 10 and kind in ("s", "inline") and txt.strip():
                by_row.setdefault(rnum, []).append((col, txt))
        for rnum in sorted(by_row):
            hints = {}
            for col, txt in by_row[rnum]:
                et = self.header_hint(txt)
                if et:
                    hints[col] = et
            if hints and len(by_row[rnum]) >= 2:
                hints["_row"] = rnum
                return hints
        return {}

    def after_write(self, replacer) -> set[str]:
        """Sayfa adı değiştiyse formüllerdeki ve tanımlı adlardaki başvuruları güncelle."""
        wb = self.tree("xl/workbook.xml").getroot()
        renames = {}
        for u, seg in self.units:
            if isinstance(u, AttrUnit) and u.part == "xl/workbook.xml" and seg.text != u.el.get("name"):
                renames[seg.text] = u.el.get("name")
        if not renames:
            return set()
        changed = {"xl/workbook.xml"}

        def fix(formula: str) -> str:
            for old, new in renames.items():
                formula = formula.replace(f"'{old}'!", f"'{new}'!")
                formula = re.sub(rf"(?<![\w']){re.escape(old)}!", f"'{new}'!", formula)
            return formula

        for dn in wb.iter(q("x", "definedName")):
            if dn.text:
                dn.text = fix(dn.text)
        for part in self.parts("xl/worksheets/sheet*.xml"):
            root = self.tree(part).getroot()
            touched = False
            for f in root.iter(q("x", "f")):
                if f.text and "!" in f.text:
                    nf = fix(f.text)
                    if nf != f.text:
                        f.text = nf
                        touched = True
            if touched:
                changed.add(part)
        # docProps/app.xml sayfa adlarını da listeler
        if "docProps/app.xml" in self.names:
            root = self.tree("docProps/app.xml").getroot()
            for el in root.iter(q("ep", "TitlesOfParts")):
                for lp in el.iter():
                    if lp.text in renames:
                        lp.text = renames[lp.text]
                        changed.add("docProps/app.xml")
        self.save_warnings.append(
            "Kişisel veri içeren sayfa adları değiştirildi; formüllerdeki başvurular güncellendi."
        )
        return changed


def _safe_sheet_name(name: str) -> str:
    return _SHEET_BAD.sub("", name)[:31] or "Sayfa"
