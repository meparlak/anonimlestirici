"""Swift arayüzünün konuştuğu motor süreci.

Standart girdiden satır satır JSON istek okur, standart çıktıya satır satır JSON cevap yazar:

    → {"id": 1, "cmd": "analyze", "paths": ["/…/sikayetler.xlsx"]}
    ← {"event": "progress", "id": 1, "done": 25, "total": 120, "message": "sikayetler.xlsx · Sayfa1!B7"}
    ← {"id": 1, "ok": true, "result": {...}}

Uzun süren bir işlemi durdurmak için {"cmd": "cancel"} gönderilir. Standart çıktıya protokol
dışında hiçbir şey yazılmaz; hata ayıklama çıktısı standart hataya gider.
"""

from __future__ import annotations

import json
import queue
import sys
import threading
import traceback
from pathlib import Path

from . import __version__
from .core.detectors.llm import list_models
from .core.engine import AnalysisResult, Cancelled, Session
from .core.report import read_mapping
from .core.reverse import ReverseReplacer, reverse_file
from .core.settings import Settings
from .core.types import Candidate, EntityType


def u16(text: str, i: int) -> int:
    """Python dizin konumunu Swift/NSString'in kullandığı UTF-16 konumuna çevirir."""
    return len(text[:i].encode("utf-16-le")) // 2


def candidate_json(c: Candidate) -> dict:
    return {
        "id": c.uid,
        "type": c.etype.value,
        "typeLabel": c.etype.label,
        "value": c.value,
        "variants": sorted(v for v in c.variants if v != c.value),
        "code": c.code,
        "count": c.count,
        "accepted": c.accepted,
        "lowConfidence": c.low_confidence and not c.manual,
        "confidence": round(c.confidence, 2),
        "sources": sorted(c.sources),
        "files": c.files,
        "occurrences": [
            {"file": o.file, "location": o.location, "context": o.context,
             "start": u16(o.context, o.start), "end": u16(o.context, o.end)}
            for o in c.occurrences[:40]
        ],
    }


class Server:
    def __init__(self, out=sys.stdout):
        self.out = out
        self.lock = threading.Lock()
        self.session = Session(Settings())
        self.result: AnalysisResult | None = None
        self.cancel_flag = threading.Event()
        self.mappings: dict[str, dict[str, str]] = {}

    # ------------------------------------------------------------ G/Ç

    def send(self, obj: dict) -> None:
        with self.lock:
            self.out.write(json.dumps(obj, ensure_ascii=False) + "\n")
            self.out.flush()

    def run(self, stream=sys.stdin) -> None:
        q: queue.Queue = queue.Queue()

        def reader():
            for line in stream:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    self.send({"ok": False, "error": "Geçersiz istek"})
                    continue
                if msg.get("cmd") == "cancel":
                    self.cancel_flag.set()
                    continue
                q.put(msg)
            q.put(None)

        threading.Thread(target=reader, daemon=True).start()
        while True:
            msg = q.get()
            if msg is None:
                break
            self.handle(msg)

    def handle(self, msg: dict) -> None:
        rid = msg.get("id")
        cmd = msg.get("cmd", "")
        fn = getattr(self, f"cmd_{cmd}", None)
        if fn is None:
            self.send({"id": rid, "ok": False, "error": f"Bilinmeyen komut: {cmd}"})
            return
        self.cancel_flag.clear()
        try:
            result = fn(msg, lambda d, t, m: self.send({"event": "progress", "id": rid, "done": d, "total": t, "message": m}))
        except Cancelled:
            self.send({"id": rid, "ok": False, "error": "", "cancelled": True})
        except Exception as e:  # noqa: BLE001 - arayüze anlaşılır mesaj gider
            traceback.print_exc(file=sys.stderr)
            self.send({"id": rid, "ok": False, "error": str(e) or e.__class__.__name__})
        else:
            self.send({"id": rid, "ok": True, "result": result})

    # ------------------------------------------------------------ yardımcılar

    def _candidates(self) -> dict:
        r = self.result
        if r is None:
            return {"candidates": [], "documents": [], "warnings": []}
        return {
            "candidates": [candidate_json(c) for c in r.candidates],
            "documents": [d.name for d in r.documents],
            "warnings": r.warnings,
        }

    def _find(self, uid: int) -> Candidate:
        if self.result is None:
            raise ValueError("Önce bir dosya taranmalı.")
        for c in self.result.candidates:
            if c.uid == uid:
                return c
        raise ValueError("Değer bulunamadı.")

    def _mapping(self, path: str) -> dict[str, str]:
        if path not in self.mappings:
            self.mappings[path] = read_mapping(Path(path))
        return self.mappings[path]

    # ------------------------------------------------------------ komutlar

    def cmd_hello(self, msg, progress):
        from .core.detectors.ner import ner_available

        from .core.settings import DEFAULT_ENABLED, DEFAULT_HEADERS

        return {
            "version": __version__,
            "ner": ner_available(),
            "types": [{"value": et.value, "label": et.label, "defaultEnabled": DEFAULT_ENABLED[et]} for et in EntityType],
            "defaults": {"headers": DEFAULT_HEADERS},
        }

    def cmd_configure(self, msg, progress):
        settings = Settings.from_dict(msg.get("settings", {}))
        self.session.settings = settings
        self.session.codebook.fmt = settings.code_format
        return {}

    def cmd_new_session(self, msg, progress):
        settings = self.session.settings
        self.session = Session(settings)
        self.result = None
        return {}

    def cmd_analyze(self, msg, progress):
        paths = [Path(p) for p in msg["paths"]]
        self.result = self.session.analyze(paths, progress, self.cancel_flag.is_set)
        return self._candidates()

    def cmd_set_accepted(self, msg, progress):
        if self.result is None:
            raise ValueError("Önce bir dosya taranmalı.")
        ids = set(msg["ids"])
        for c in self.result.candidates:
            if c.uid in ids:
                c.accepted = bool(msg["accepted"])
        self.session.codebook.assign(self.result.candidates)
        return self._candidates()

    def cmd_set_type(self, msg, progress):
        c = self._find(msg["id"])
        self.session.change_type(self.result, c, EntityType(msg["type"]))
        return self._candidates()

    def cmd_add_manual(self, msg, progress):
        if self.result is None:
            raise ValueError("Önce bir dosya taranmalı.")
        c = self.session.add_manual(self.result, msg["value"], EntityType(msg["type"]))
        out = self._candidates()
        out["addedId"] = c.uid
        out["addedCount"] = c.count
        return out

    def cmd_save(self, msg, progress):
        if self.result is None:
            raise ValueError("Kaydedilecek bir tarama yok.")
        res = self.session.save(self.result, Path(msg["outDir"]), progress)
        return {
            "outputs": [str(p) for p in res.outputs],
            "mapping": str(res.mapping),
            "replaced": res.replaced,
            "distinct": res.distinct,
            "skipped": res.skipped,
            "warnings": res.warnings,
        }

    def cmd_read_mapping(self, msg, progress):
        self.mappings.pop(msg["path"], None)
        return {"count": len(self._mapping(msg["path"]))}

    def cmd_reverse_text(self, msg, progress):
        r = ReverseReplacer(self._mapping(msg["mappingPath"]))
        text = msg["text"]
        spans = sorted(r.spans(text), key=lambda s: s.start)
        out = text
        for sp in reversed(spans):
            out = out[: sp.start] + sp.replacement + out[sp.end :]
        return {
            "text": out,
            "spans": [{"start": u16(text, s.start), "end": u16(text, s.end), "replacement": s.replacement} for s in spans],
            "replaced": len(spans),
            "unknown": sorted(r.stats.unknown),
        }

    def cmd_reverse_file(self, msg, progress):
        out, stats = reverse_file(Path(msg["path"]), Path(msg["mappingPath"]), Path(msg["outDir"]))
        return {"output": str(out), "replaced": stats.replaced, "unknown": sorted(stats.unknown or [])}

    def cmd_llm_models(self, msg, progress):
        return {"models": list_models(msg["url"])}


def serve() -> int:
    # Protokol yalnızca UTF-8 konuşur
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    Server().run()
    return 0
