"""Komut satırı arayüzü.

    python -m anonimlestirici serve              # Swift arayüzü için motor süreci
    python -m anonimlestirici tara dosya.xlsx    # bulguları listeler, dosya yazmaz
    python -m anonimlestirici anonimlestir dosya.xlsx [dosya2.docx ...] [-o klasör]
    python -m anonimlestirici geri-cevir -t dosya_eslestirme.xlsx cevap.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .core.engine import Session
from .core.formats import UnsupportedFile
from .core.settings import Settings


def _session(args) -> Session:
    s = Settings() if args.varsayilan else Settings.load()
    return Session(s)


def cmd_scan(args) -> int:
    session = _session(args)
    result = session.analyze([Path(p) for p in args.dosyalar])
    for w in result.warnings:
        print(f"! {w}", file=sys.stderr)
    for c in result.candidates:
        mark = "x" if c.accepted else " "
        print(f"[{mark}] {c.code or '-':<14} {c.etype.label:<13} {c.count:>4}  {c.value}")
    print(f"\n{len(result.candidates)} farklı değer, {sum(c.count for c in result.candidates)} geçiş.")
    return 0


def cmd_anonymize(args) -> int:
    session = _session(args)
    result = session.analyze([Path(p) for p in args.dosyalar])
    for w in result.warnings:
        print(f"! {w}", file=sys.stderr)
    res = session.save(result, Path(args.cikti) if args.cikti else None)
    for o in res.outputs:
        print(f"Anonim dosya:        {o}")
    print(f"Eşleştirme tablosu:  {res.mapping}")
    print(f"{res.replaced} geçiş, {res.distinct} farklı değer değiştirildi; {res.skipped} değer atlandı.")
    for w in res.warnings:
        print(f"! {w}", file=sys.stderr)
    return 0


def cmd_reverse(args) -> int:
    from .core.reverse import reverse_file, reverse_text

    table = Path(args.tablo)
    if args.dosya == "-":
        text, stats = reverse_text(sys.stdin.read(), table)
        sys.stdout.write(text)
    else:
        out, stats = reverse_file(Path(args.dosya), table)
        print(f"Geri çevrilmiş dosya: {out}")
    print(f"{stats.replaced} kod çevrildi.", file=sys.stderr)
    if stats.unknown:
        print(f"Tabloda bulunmayan kodlar: {', '.join(sorted(stats.unknown))}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    argv = [a for a in argv if not a.startswith("-psn_")]  # eski macOS sürümlerinin eklediği süreç numarası
    if argv[:1] == ["serve"]:
        from .server import serve

        return serve()
    p = argparse.ArgumentParser(prog="anonimlestirici", description="Dosyalardaki kişisel verileri yerelde anonimleştirir.")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("--varsayilan", action="store_true", help="kayıtlı ayarlar yerine varsayılan ayarları kullan")
    sub = p.add_subparsers(dest="komut", required=True)

    a = sub.add_parser("tara", help="bulguları listele, dosya yazma")
    a.add_argument("dosyalar", nargs="+")
    a.set_defaults(func=cmd_scan)

    b = sub.add_parser("anonimlestir", help="anonim dosya ve eşleştirme tablosu üret")
    b.add_argument("dosyalar", nargs="+")
    b.add_argument("-o", "--cikti", help="çıktı klasörü (varsayılan: girdinin klasörü)")
    b.set_defaults(func=cmd_anonymize)

    c = sub.add_parser("geri-cevir", help="kodları eşleştirme tablosuyla gerçek değerlere çevir")
    c.add_argument("-t", "--tablo", required=True, help="..._eslestirme.xlsx dosyası")
    c.add_argument("dosya", help="çevrilecek dosya ya da standart girdi için '-'")
    c.set_defaults(func=cmd_reverse)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (UnsupportedFile, ValueError, FileNotFoundError) as e:
        print(f"Hata: {e}", file=sys.stderr)
        return 2
