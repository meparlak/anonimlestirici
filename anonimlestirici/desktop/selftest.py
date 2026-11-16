"""Paketlenmiş masaüstü uygulamasının öz-testi: `Anonimlestirici.exe --selftest --log dosya.txt`

Arayüz açılmadan motoru, dil modelini, kaydetmeyi ve geri çevirmeyi uçtan uca dener.
Windows'ta pencereli uygulamanın konsolu olmadığı için sonuç ayrıca bir dosyaya yazılır.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from pathlib import Path

from ..server import Server
from . import prefs as P

SAMPLE = """Toplantı notu
Kıvılcım Aras ile John Smith toplantıya katıldı; Yıldız Makine A.Ş. temsilcisi de oradaydı.
Ahmet Yılmaz (TC: 10000000078, Tel: 0532 123 45 67) Satın Alma Birimi adına konuştu.
"""


def run(log_path: str | None = None) -> int:
    lines: list[str] = []

    def say(s: str) -> None:
        lines.append(s)
        print(s, flush=True)

    ok = False
    work = Path(tempfile.mkdtemp(prefix="anonim-ozt-"))
    try:
        say("öz-test başlıyor")
        server = Server(io.StringIO())
        hello = server.cmd_hello({}, None)
        say(f"motor: {hello['version']}, dil modeli: {'var' if hello['ner'] else 'yok'}, {len(hello['types'])} tür")
        server.cmd_configure({"settings": P.engine_settings(dict(P.DEFAULTS))}, None)
        src = work / "ornek.txt"
        src.write_text(SAMPLE, encoding="utf-8")
        res = server.cmd_analyze({"paths": [str(src)]}, lambda *a: None)
        for c in res["candidates"]:
            say(f"  {'x' if c['accepted'] else ' '} {c['code']:<13} {c['value']}  [{', '.join(c['sources'])}]")
        out_dir = work / "cikti"
        out_dir.mkdir()
        saved = server.cmd_save({"outDir": str(out_dir)}, lambda *a: None)
        out = Path(saved["outputs"][0]).read_text(encoding="utf-8")
        say("anonim çıktı:\n" + out)
        back = server.cmd_reverse_text({"text": out, "mappingPath": saved["mapping"]}, None)
        ok = (
            "Kıvılcım Aras" in back["text"]
            and "10000000078" in back["text"]
            and "Ahmet" not in out
            and hello["ner"]
        )
        say("SONUÇ: BAŞARILI" if ok else "SONUÇ: BAŞARISIZ\n" + back["text"])
    except Exception as e:  # noqa: BLE001
        say(f"SONUÇ: HATA {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if log_path:
            Path(log_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0 if ok else 1

