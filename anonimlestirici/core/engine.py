"""Anonimleştirme oturumu: tarama, önizleme için adaylar, kod atama ve dosya yazma."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from .detectors import build_detectors
from .detectors.names import STOPWORDS, lexicon
from .detectors.patterns import canonical_key
from .formats import Document, open_document
from .settings import Settings
from .textutil import bounded, ci_pattern, fold, normalize_key, snippet
from .types import Candidate, EntityType, Finding, Occurrence, Segment

Progress = Callable[[int, int, str], None]  # (yapılan, toplam, açıklama)


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- kodlar


def _letters(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def render_code(et: EntityType, n: int, fmt: str) -> str:
    if fmt == "plain":
        return f"{et.value}_{n}"
    if fmt == "letter":
        word = {
            EntityType.KISI: "Kişi",
            EntityType.EPOSTA: "E-posta",
            EntityType.OZEL: "Özel",
            EntityType.TARIH: "Tarih",
            EntityType.BIRIM: "Birim",
            EntityType.VERGI: "Vergi",
            EntityType.FINANS: "Finans",
            EntityType.SAGLIK: "Sağlık",
        }.get(et, et.value.capitalize())
        return f"{word} {_letters(n)}"
    return f"[{et.value}_{n}]"


class Codebook:
    """(tür, anahtar) → sıra numarası. Bir oturum boyunca bütün dosyalarda ortaktır."""

    def __init__(self, fmt: str = "bracket"):
        self.fmt = fmt
        self.numbers: dict[tuple[EntityType, str], int] = {}
        self.counters: dict[EntityType, int] = {}

    def assign(self, candidates: Iterable[Candidate], commit: bool = False) -> None:
        numbers = self.numbers if commit else dict(self.numbers)
        counters = self.counters if commit else dict(self.counters)
        for c in candidates:
            if not c.accepted:
                c.code = ""
                continue
            k = (c.etype, c.key)
            if k not in numbers:
                counters[c.etype] = counters.get(c.etype, 0) + 1
                numbers[k] = counters[c.etype]
            c.code = render_code(c.etype, numbers[k], self.fmt)


# ---------------------------------------------------------------- eşleştirici


@dataclass
class Span:
    start: int
    end: int
    replacement: str


class Matcher:
    """Kabul edilen değerlerin bütün yazımlarını bulur.

    Değerler ilk kelimelerine göre bir sözlükte tutulur. Metindeki her kelime için yalnızca o
    kelimeyle başlayan değerler denenir; böylece süre değer sayısıyla değil metin uzunluğuyla artar.
    """

    _WORD = re.compile(r"\w+")

    def __init__(self, candidates: Iterable[Candidate], exclude: Iterable[str] = ()):
        self.lookup: dict[str, Candidate] = {}
        by_first: dict[str, list[str]] = {}
        others: list[str] = []
        for c in candidates:
            for v in c.variants | {c.value}:
                v = v.strip()
                if len(v) < 2:
                    continue
                self.lookup.setdefault(normalize_key(v), c)
                m = self._WORD.match(v)
                if m:
                    by_first.setdefault(fold(m.group()), []).append(v)
                else:
                    others.append(v)  # "(0264) …", "+90 …" gibi kelimeyle başlamayan değerler
        self.index: dict[str, list[re.Pattern]] = {}
        for key, values in by_first.items():
            uniq = sorted(set(values), key=len, reverse=True)
            self.index[key] = [re.compile(bounded(ci_pattern(v))) for v in uniq]
        others = sorted(set(others), key=len, reverse=True)
        self.others = re.compile("|".join(bounded(ci_pattern(v)) for v in others)) if others else None
        ex = [e for e in exclude if e.strip()]
        self.ex_rx = re.compile("|".join(bounded(ci_pattern(e)) for e in ex)) if ex else None

    def find(self, text: str) -> list[tuple[int, int, Candidate]]:
        if not text or (not self.index and not self.others):
            return []
        hits: list[tuple[int, int]] = []
        for w in self._WORD.finditer(text):
            pats = self.index.get(fold(w.group()))
            if not pats:
                continue
            for rx in pats:
                m = rx.match(text, w.start())
                if m:
                    hits.append((m.start(), m.end()))
                    break
        if self.others:
            hits += [(m.start(), m.end()) for m in self.others.finditer(text)]
        if not hits:
            return []
        blocked = [(m.start(), m.end()) for m in self.ex_rx.finditer(text)] if self.ex_rx else []
        out = []
        last_end = -1
        # soldan sağa, aynı yerde başlayanlardan en uzunu
        for s, e in sorted(hits, key=lambda h: (h[0], -h[1])):
            if s < last_end:
                continue
            if any(a <= s and e <= b for a, b in blocked):
                continue
            frag = text[s:e]
            c = self.lookup.get(normalize_key(frag))
            if c is None:
                continue
            if c.etype == EntityType.KISI and " " not in frag and not frag[:1].isupper():
                # Tek kelimelik ad küçük harfle geçiyorsa büyük ihtimalle sıradan kelimedir ("emin", "ali")
                continue
            out.append((s, e, c))
            last_end = e
        return out


class Replacer:
    """Biçim modüllerinin kullandığı arayüz: metindeki değiştirilecek aralıkları verir."""

    def __init__(self, matcher: Matcher, whole: dict[str, str] | None = None):
        self.matcher = matcher
        self.whole = whole or {}

    def spans(self, text: str, segment: Segment | None = None) -> list[Span]:
        return [Span(s, e, c.code) for s, e, c in self.matcher.find(text) if c.accepted and c.code]

    def apply(self, text: str, segment: Segment | None = None) -> str:
        spans = self.spans(text, segment)
        for sp in sorted(spans, key=lambda x: x.start, reverse=True):
            text = text[: sp.start] + sp.replacement + text[sp.end :]
        return text


def resolve_overlaps(findings: list[Finding]) -> list[Finding]:
    kept: list[Finding] = []
    for f in sorted(findings, key=lambda f: f.score, reverse=True):
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f.start)


# ---------------------------------------------------------------- oturum


@dataclass
class AnalysisResult:
    documents: list[Document]
    candidates: list[Candidate]
    warnings: list[str] = field(default_factory=list)

    def by_key(self) -> dict[tuple[EntityType, str], Candidate]:
        return {(c.etype, c.key): c for c in self.candidates}


@dataclass
class SaveResult:
    outputs: list[Path]
    mapping: Path
    replaced: int
    distinct: int
    skipped: int
    warnings: list[str]


class Session:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings.load()
        self.codebook = Codebook(self.settings.code_format)
        self.committed: dict[tuple[EntityType, str], Candidate] = {}
        self.processed: list[str] = []

    # --- tarama

    def analyze(self, paths: list[Path], progress: Progress | None = None, cancel: Callable[[], bool] | None = None) -> AnalysisResult:
        self.codebook.fmt = self.settings.code_format
        docs: list[Document] = []
        warnings: list[str] = []
        for p in paths:
            doc = open_document(Path(p), self.settings)
            docs.append(doc)
            warnings.extend(f"{doc.name}: {w}" for w in doc.warnings)

        detectors = build_detectors(self.settings)
        exclude = self.settings.exclude_entries()
        ex_rx = re.compile("|".join(bounded(ci_pattern(e)) for e in exclude)) if exclude else None
        ex_keys = {normalize_key(e) for e in exclude}

        all_segments: list[tuple[Document, Segment]] = [(d, s) for d in docs for s in d.segments]
        total = len(all_segments)
        # Toplu çalışan dedektörler (NER modeli) bütün parçaları bir kerede işler
        for d in detectors:
            prepare = getattr(d, "prepare", None)
            if prepare:
                prepare([s for _, s in all_segments], progress, cancel)
        cands: dict[tuple[EntityType, str], Candidate] = {}

        for idx, (doc, seg) in enumerate(all_segments):
            if cancel and cancel():
                raise Cancelled()
            if progress and (idx % 25 == 0 or idx == total - 1):
                progress(idx + 1, total, f"{doc.name} · {seg.location}")
            if not seg.text or not seg.text.strip():
                continue
            found: list[Finding] = []
            for d in detectors:
                found.extend(d.detect(seg))
            if ex_rx and found:
                blocked = [(m.start(), m.end()) for m in ex_rx.finditer(seg.text)]
                found = [f for f in found if not any(a <= f.start and f.end <= b for a, b in blocked)]
            found = [f for f in found if normalize_key(f.text) not in ex_keys]
            for f in resolve_overlaps(found):
                key = canonical_key(f.etype, f.text)
                if not key:
                    continue
                c = cands.get((f.etype, key))
                if c is None:
                    c = Candidate(etype=f.etype, key=key, value=f.text.strip())
                    cands[(f.etype, key)] = c
                c.variants.add(f.text.strip())
                c.sources.add(f.source)
                c.confidence = max(c.confidence, f.confidence)

        if self.settings.name_aliases:
            self._merge_name_aliases(cands)

        # Önceki dosyalarda onaylanmış değerler bu dosyada da aynı kodu almalı
        for k, prev in self.committed.items():
            if k in cands:
                cands[k].variants |= prev.variants
            else:
                cands[k] = Candidate(etype=prev.etype, key=prev.key, value=prev.value, variants=set(prev.variants),
                                     sources={"Önceki dosya"}, confidence=1.0)

        candidates = list(cands.values())
        for c in candidates:
            c.accepted = c.confidence >= 0.5
        result = AnalysisResult(docs, candidates, warnings)
        self.recount(result)
        return result

    def _merge_name_aliases(self, cands: dict[tuple[EntityType, str], Candidate]) -> None:
        """'Ahmet Yılmaz' varsa ve dosyada tek Ahmet oysa, tek başına geçen 'Ahmet' / 'Yılmaz Bey' aynı kişidir."""
        lex = lexicon()
        persons = [c for c in cands.values() if c.etype == EntityType.KISI and len(c.value.split()) >= 2]
        alias_owner: dict[str, Candidate | None] = {}
        for p in persons:
            words = p.value.split()
            for w in {words[0], words[-1]}:
                fw = fold(w)
                if fw in lex["ambiguous"] or fw in STOPWORDS or len(fw) < 3:
                    continue
                key = normalize_key(w)
                if key in alias_owner and alias_owner[key] is not p:
                    alias_owner[key] = None  # iki kişide ortak: belirsiz
                else:
                    alias_owner[key] = p
        for (et, key), c in list(cands.items()):
            if et != EntityType.KISI or len(c.value.split()) != 1:
                continue
            owner = alias_owner.get(key)
            if owner is not None and owner is not c:
                owner.variants |= c.variants
                owner.sources |= c.sources
                del cands[(et, key)]
        # Soyadının unvanla tek başına geçmesi: "Yılmaz Bey", "Sayın Kaya"
        for key, owner in alias_owner.items():
            if owner is None:
                continue
            owner.variants.add(next((w for w in owner.value.split() if normalize_key(w) == key), key))

    def recount(self, result: AnalysisResult) -> None:
        """Adayların bütün geçişlerini (dedektörün kaçırdıkları dahil) yeniden sayar ve kodları günceller."""
        for c in result.candidates:
            c.occurrences = []
        matcher = Matcher(result.candidates, self.settings.exclude_entries())
        order = 0
        for doc in result.documents:
            for seg in doc.segments:
                order += 1
                for s, e, c in matcher.find(seg.text):
                    ctx, cs, ce = snippet(seg.text, s, e)
                    c.occurrences.append(Occurrence(doc.name, seg.location, ctx, cs, ce, order))
        # Hiç geçişi kalmayan aday (ör. yalnızca dışlanan bağlamda geçen) listeden düşer
        result.candidates[:] = [c for c in result.candidates if c.occurrences or c.manual]
        result.candidates.sort(key=lambda c: c.occurrences[0].order if c.occurrences else 10**9)
        self.codebook.assign(result.candidates)

    def add_manual(self, result: AnalysisResult, value: str, et: EntityType) -> Candidate:
        key = canonical_key(et, value)
        existing = result.by_key().get((et, key))
        if existing:
            existing.accepted = True
            existing.variants.add(value.strip())
            c = existing
        else:
            c = Candidate(etype=et, key=key, value=value.strip(), variants={value.strip()}, confidence=1.0,
                          sources={"Elle eklendi"}, manual=True)
            result.candidates.append(c)
        self.recount(result)
        return c

    def change_type(self, result: AnalysisResult, cand: Candidate, et: EntityType) -> None:
        if cand.etype == et:
            return
        new_key = canonical_key(et, cand.value)
        other = result.by_key().get((et, new_key))
        if other and other is not cand:
            other.variants |= cand.variants
            other.sources |= cand.sources
            result.candidates.remove(cand)
        else:
            cand.etype, cand.key = et, new_key
        self.recount(result)

    # --- yazma

    def save(self, result: AnalysisResult, out_dir: Path | None = None, progress: Progress | None = None) -> SaveResult:
        from .report import write_mapping

        accepted = [c for c in result.candidates if c.accepted]
        self.codebook.assign(result.candidates, commit=True)
        matcher = Matcher(accepted, self.settings.exclude_entries())
        replacer = Replacer(matcher)
        outputs: list[Path] = []
        warnings: list[str] = []
        for i, doc in enumerate(result.documents):
            if progress:
                progress(i, len(result.documents), doc.name)
            target_dir = out_dir or (Path(self.settings.output_dir) if self.settings.output_dir else doc.path.parent)
            out = unique_path(target_dir / f"{doc.path.stem}{self.settings.output_suffix}{doc.path.suffix}")
            doc.save(out, replacer)
            warnings.extend(f"{doc.name}: {w}" for w in doc.save_warnings)
            outputs.append(out)
            self.processed.append(doc.name)

        for c in accepted:
            self.committed[(c.etype, c.key)] = c
        first = result.documents[0]
        target_dir = out_dir or (Path(self.settings.output_dir) if self.settings.output_dir else first.path.parent)
        stem = first.path.stem if len(result.documents) == 1 else f"{first.path.stem}_ve_{len(result.documents) - 1}_dosya"
        mapping = unique_path(target_dir / f"{stem}_eslestirme.xlsx")
        all_known = list(self.committed.values())
        skipped = [c for c in result.candidates if not c.accepted]
        write_mapping(mapping, all_known, skipped, self, [d.name for d in result.documents])
        return SaveResult(
            outputs=outputs,
            mapping=mapping,
            replaced=sum(c.count for c in accepted),
            distinct=len(accepted),
            skipped=len(skipped),
            warnings=warnings,
        )


def unique_path(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        return p
    i = 2
    while True:
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
        i += 1


__all__ = ["Session", "AnalysisResult", "SaveResult", "Codebook", "Matcher", "Replacer", "Span", "Cancelled",
           "render_code"]
