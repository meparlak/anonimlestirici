# Windows paketi: python -m PyInstaller packaging/windows/anonimlestirici-win.spec
# Çıktı: dist/windows/Anonimlestirici/Anonimlestirici.exe (+ _internal klasörü)
# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH).parent.parent
PKG = ROOT / "anonimlestirici"

datas = [
    (str(PKG / "data" / "*.txt"), "anonimlestirici/data"),
    (str(PKG / "desktop" / "ui" / "*"), "anonimlestirici/desktop/ui"),
]
model = PKG / "models" / "ner"
if (model / "model.onnx").exists():
    datas.append((str(model / "*"), "anonimlestirici/models/ner"))
licenses = ROOT / "build" / "licenses"
if licenses.exists():
    datas.append((str(licenses), "Lisanslar"))

a = Analysis(
    [str(ROOT / "packaging" / "windows" / "launcher_win.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=["anonimlestirici.data", "anonimlestirici.server", "webview.platforms.winforms"],
    excludes=["tkinter", "unittest", "pydoc", "pytest", "PySide6", "PyQt5", "PyQt6", "IPython", "matplotlib", "scipy", "pandas"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name="Anonimlestirici", console=False,
    icon=str(ROOT / "packaging" / "windows" / "Anonimlestirici.ico"),
    version=str(ROOT / "build" / "version_info.txt") if (ROOT / "build" / "version_info.txt").exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Anonimlestirici")
