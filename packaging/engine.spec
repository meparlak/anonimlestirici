# Motor yardımcı uygulaması (AnonimEngine.app): python -m PyInstaller packaging/engine.spec
# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = {}
exec((ROOT / "anonimlestirici" / "__init__.py").read_text(), VERSION)
BUNDLE_ID = os.environ.get("BUNDLE_ID", "io.github.meparlak.anonimlestirici")

datas = [(str(ROOT / "anonimlestirici" / "data" / "*.txt"), "anonimlestirici/data")]
model = ROOT / "anonimlestirici" / "models" / "ner"
if (model / "model.onnx").exists():
    datas.append((str(model / "*"), "anonimlestirici/models/ner"))

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["anonimlestirici.data", "anonimlestirici.server"],
    excludes=["tkinter", "unittest", "pydoc", "pytest", "PySide6", "IPython", "matplotlib", "scipy", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="anonim-engine", console=True,
          argv_emulation=False, codesign_identity=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="anonim-engine")
app = BUNDLE(
    coll,
    name="AnonimEngine.app",
    bundle_identifier=BUNDLE_ID + ".engine",
    version=VERSION["__version__"],
    info_plist={"LSBackgroundOnly": True, "LSMinimumSystemVersion": "13.0", "CFBundleName": "AnonimEngine"},
)
