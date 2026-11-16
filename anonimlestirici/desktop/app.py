"""Windows masaüstü uygulaması: pywebview penceresi + aynı Python motoru.

Arayüz `ui/` klasöründeki HTML/CSS/JS dosyalarıdır ve Windows'ta Microsoft Edge WebView2 ile
gösterilir. Bütün dosyalar uygulamanın içindedir; internete bağlanılmaz. Arayüz bu dosyadaki
`Api` sınıfının yöntemlerini `window.pywebview.api.<ad>()` ile çağırır.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from pathlib import Path

from .. import __version__
from ..core.engine import Cancelled
from ..core.formats import SUPPORTED, check_supported
from ..core.types import EntityType
from ..server import Server
from . import prefs as P

UI_DIR = Path(__file__).resolve().parent / "ui"


def _ui_dir() -> Path:
    if getattr(sys, "_MEIPASS", None):  # PyInstaller paketi
        return Path(sys._MEIPASS) / "anonimlestirici" / "desktop" / "ui"
    return UI_DIR


class Api:
    """Arayüzün çağırdığı işlevler. Her çağrı pywebview tarafından ayrı bir iş parçacığında çalışır."""

    def __init__(self, dialogs=None):
        self.server = Server(io.StringIO())
        self.prefs = P.load()
        self.window = None
        self.inputs: list[str] = []
        # Testlerde pencere yerine sahte diyaloglar verilebilir
        self._dialogs = dialogs

    # ------------------------------------------------------------ yardımcılar

    def _js(self, code: str) -> None:
        if self.window is not None:
            self.window.evaluate_js(code)

    def _progress(self, done: int, total: int, msg: str) -> None:
        self._js(f"app.onProgress({json.dumps({'done': done, 'total': total, 'message': msg}, ensure_ascii=False)})")

    def _configure(self) -> None:
        self.server.cmd_configure({"settings": P.engine_settings(self.prefs)}, None)

    def _dialog(self, kind: str, **kw):
        if self._dialogs is not None:
            return self._dialogs(kind, **kw)
        import webview

        mapping = {"open": webview.OPEN_DIALOG, "folder": webview.FOLDER_DIALOG}
        return self.window.create_file_dialog(mapping[kind], **kw)

    @staticmethod
    def _ok(**data) -> dict:
        return {"ok": True, **data}

    @staticmethod
    def _err(e: Exception | str) -> dict:
        return {"ok": False, "error": str(e) or type(e).__name__}

    # ------------------------------------------------------------ genel

    def hello(self) -> dict:
        h = self.server.cmd_hello({}, None)
        return self._ok(**h, prefs=self.prefs, platform=sys.platform, appVersion=__version__)

    def set_prefs(self, prefs: dict) -> dict:
        self.prefs.update({k: v for k, v in prefs.items() if k in P.DEFAULTS})
        P.save(self.prefs)
        return self._ok(prefs=self.prefs)

    def choose_files(self) -> list[str]:
        types = ("Desteklenen dosyalar (" + ";".join(f"*{e}" for e in SUPPORTED) + ")",)
        res = self._dialog("open", allow_multiple=True, file_types=types)
        return list(res or [])

    def choose_output_folder(self) -> dict:
        res = self._dialog("folder", directory=self.prefs.get("outputFolder") or str(Path.home()))
        if res:
            self.prefs["outputFolder"] = res[0]
            P.save(self.prefs)
        return self._ok(prefs=self.prefs)

    # ------------------------------------------------------------ anonimleştirme

    def analyze(self, paths: list[str]) -> dict:
        problems, ok = [], []
        for p in paths:
            path = Path(p)
            if path.is_dir():
                problems.append(f"{path.name}: Klasörler desteklenmiyor, dosyaları seçin.")
                continue
            msg = check_supported(path)
            (problems.append(f"{path.name}: {msg}") if msg else ok.append(str(path)))
        if not ok:
            return {"ok": False, "error": "\n\n".join(problems) or "Dosya seçilmedi."}
        self.inputs = ok
        try:
            self._configure()
            self.server.cancel_flag.clear()
            res = self.server.cmd_analyze({"paths": ok}, self._progress)
        except Cancelled:
            return {"ok": False, "cancelled": True}
        except Exception as e:  # noqa: BLE001
            return self._err(f"{e}\n\nDosya başka bir programda açıksa kapatıp yeniden deneyin. Parola korumalı dosyalar desteklenmiyor.")
        return self._ok(**res, problems=problems)

    def cancel(self) -> dict:
        self.server.cancel_flag.set()
        return self._ok()

    def set_accepted(self, ids: list[int], accepted: bool) -> dict:
        try:
            return self._ok(**self.server.cmd_set_accepted({"ids": ids, "accepted": accepted}, None))
        except Exception as e:  # noqa: BLE001
            return self._err(e)

    def set_type(self, cid: int, etype: str) -> dict:
        try:
            return self._ok(**self.server.cmd_set_type({"id": cid, "type": etype}, None))
        except Exception as e:  # noqa: BLE001
            return self._err(e)

    def add_manual(self, value: str, etype: str) -> dict:
        try:
            return self._ok(**self.server.cmd_add_manual({"value": value, "type": etype}, None))
        except Exception as e:  # noqa: BLE001
            return self._err(e)

    def exclude(self, cid: int, value: str) -> dict:
        terms = list(self.prefs.get("excludeTerms") or [])
        if value not in terms:
            terms.append(value)
            self.prefs["excludeTerms"] = terms
            P.save(self.prefs)
        return self.set_accepted([cid], False)

    def save(self) -> dict:
        folder = None
        if not self.prefs.get("askOutputFolder", True) and self.prefs.get("outputFolder"):
            folder = self.prefs["outputFolder"]
        else:
            start = str(Path(self.inputs[0]).parent) if self.inputs else str(Path.home())
            res = self._dialog("folder", directory=start)
            folder = res[0] if res else None
        if not folder:
            return {"ok": False, "cancelled": True}
        try:
            res = self.server.cmd_save({"outDir": folder}, self._progress)
        except Exception as e:  # noqa: BLE001
            return self._err(e)
        for o in res["outputs"]:
            P.add_recent(self.prefs, Path(o).name, o, res["distinct"])
        P.save(self.prefs)
        return self._ok(**res)

    def new_session(self) -> dict:
        self.server.cmd_new_session({}, None)
        self.inputs = []
        return self._ok()

    # ------------------------------------------------------------ geri çevirme

    def pick_mapping(self) -> dict:
        res = self._dialog("open", allow_multiple=False, file_types=("Eşleştirme tablosu (*.xlsx)",))
        if not res:
            return {"ok": False, "cancelled": True}
        path = res[0]
        try:
            info = self.server.cmd_read_mapping({"path": path}, None)
        except Exception as e:  # noqa: BLE001
            return self._err(e)
        return self._ok(path=path, name=Path(path).name, count=info["count"])

    def reverse_text(self, text: str, mapping_path: str) -> dict:
        try:
            return self._ok(**self.server.cmd_reverse_text({"text": text, "mappingPath": mapping_path}, None))
        except Exception as e:  # noqa: BLE001
            return self._err(e)

    def reverse_file(self, mapping_path: str) -> dict:
        types = ("Desteklenen dosyalar (" + ";".join(f"*{e}" for e in SUPPORTED) + ")",)
        res = self._dialog("open", allow_multiple=False, file_types=types)
        if not res:
            return {"ok": False, "cancelled": True}
        src = Path(res[0])
        folder = self._dialog("folder", directory=str(src.parent))
        if not folder:
            return {"ok": False, "cancelled": True}
        try:
            out = self.server.cmd_reverse_file({"path": str(src), "mappingPath": mapping_path, "outDir": folder[0]}, None)
        except Exception as e:  # noqa: BLE001
            return self._err(e)
        self.reveal(out["output"])
        return self._ok(**out, name=Path(out["output"]).name)

    # ------------------------------------------------------------ dosya sistemi

    def open_path(self, p: str) -> dict:
        try:
            if sys.platform == "win32":
                os.startfile(p)  # noqa: S606
            else:
                subprocess.run(["open", p], check=False)
        except OSError as e:
            return self._err(e)
        return self._ok()

    def reveal(self, p: str) -> dict:
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(p)], check=False)
            else:
                subprocess.run(["open", "-R", p], check=False)
        except OSError as e:
            return self._err(e)
        return self._ok()

    def copy_text(self, text: str) -> dict:
        try:
            if sys.platform == "win32":
                _win_clipboard(text)
            else:
                subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=False)
        except OSError as e:
            return self._err(e)
        return self._ok()

    def types(self) -> list[dict]:
        return [{"value": et.value, "label": et.label} for et in EntityType]


def _win_clipboard(text: str) -> None:
    """Windows panosuna Unicode metin yazar (ek kütüphane gerektirmez)."""
    import ctypes
    from ctypes import wintypes

    CF_UNICODETEXT, GMEM_MOVEABLE = 13, 0x0002
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.restype = wintypes.LPVOID
    data = text.encode("utf-16-le") + b"\x00\x00"
    if not user32.OpenClipboard(None):
        raise OSError("Pano açılamadı")
    try:
        user32.EmptyClipboard()
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        ptr = kernel32.GlobalLock(h)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
    finally:
        user32.CloseClipboard()


def _install_drop_handler(window, api: Api) -> None:
    """Pencereye sürüklenen dosyaların tam yolunu arayüze iletir."""
    from webview.dom import DOMEventHandler

    def on_drop(e):
        files = e.get("dataTransfer", {}).get("files", [])
        paths = [f.get("pywebviewFullPath") for f in files if f.get("pywebviewFullPath")]
        if paths:
            window.evaluate_js(f"app.onFilesDropped({json.dumps(paths, ensure_ascii=False)})")

    def ignore(e):
        pass

    window.dom.document.events.dragover += DOMEventHandler(ignore, True, True)
    window.dom.document.events.drop += DOMEventHandler(on_drop, True, True)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selftest" in argv:
        from .selftest import run

        log = argv[argv.index("--log") + 1] if "--log" in argv and argv.index("--log") + 1 < len(argv) else None
        return run(log)

    import webview

    api = Api()
    window = webview.create_window(
        "Anonimleştirici",
        url=str(_ui_dir() / "index.html"),
        js_api=api,
        width=1120,
        height=760,
        min_size=(880, 600),
        background_color="#F3F3F3",
        text_select=True,
    )
    api.window = window
    window.events.loaded += lambda: _install_drop_handler(window, api)
    webview.start(private_mode=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
