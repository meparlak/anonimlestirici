"""Uygulamanın içine giren üçüncü taraf bileşenlerin lisans metinlerini toplar.

    python packaging/collect_licenses.py <hedef klasör>
"""

from __future__ import annotations

import shutil
import sys
import sysconfig
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ["lxml", "openpyxl", "et_xmlfile", "onnxruntime", "tokenizers", "numpy", "pyinstaller"]
NAMES = ("LICENSE", "LICENCE", "COPYING", "NOTICE", "AUTHORS")


def main() -> int:
    dest = Path(sys.argv[1])
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in PACKAGES:
        try:
            dist = distribution(name)
        except PackageNotFoundError:
            continue
        out = dest / f"{dist.metadata['Name']}-{dist.version}"
        out.mkdir()
        for f in dist.files or []:
            if any(f.name.upper().startswith(n) for n in NAMES) or "/licenses/" in str(f).lower():
                src = Path(dist.locate_file(f))
                if src.is_file():
                    shutil.copy(src, out / f.name)
        (out / "METADATA.txt").write_text(
            f"{dist.metadata['Name']} {dist.version}\nLisans: {dist.metadata.get('License-Expression') or dist.metadata.get('License') or ''}\n"
            f"Adres: {dist.metadata.get('Home-page') or ''}\n",
            encoding="utf-8",
        )
    # Python yorumlayıcısı (PSF lisansı; OpenSSL, zstd, xz, mpdecimal bildirimlerini de içerir)
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    for cand in (stdlib / "LICENSE.txt", stdlib.parent / "LICENSE.txt"):
        if cand.is_file():
            shutil.copy(cand, dest / "Python-LICENSE.txt")
            break
    # Dil modeli
    model = ROOT / "anonimlestirici" / "models" / "ner"
    if model.exists():
        (dest / "modernbert-tr-pii-ner").mkdir()
        for f in ("README.md", "KAYNAK.txt"):
            if (model / f).exists():
                shutil.copy(model / f, dest / "modernbert-tr-pii-ner" / f)
        shutil.copy(ROOT / "packaging" / "licenses" / "Apache-2.0.txt", dest / "modernbert-tr-pii-ner" / "LICENSE-Apache-2.0.txt")
    shutil.copy(ROOT / "LICENSE", dest / "Anonimlestirici-LICENSE.txt")
    shutil.copy(ROOT / "THIRD_PARTY_NOTICES.md", dest / "THIRD_PARTY_NOTICES.md")
    print(f"Lisanslar: {dest} ({sum(1 for _ in dest.rglob('*') if _.is_file())} dosya)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
