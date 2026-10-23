"""Düz metin (.txt, .md)."""

from __future__ import annotations

from pathlib import Path

from ..types import Segment
from . import Document

ENCODINGS = ("utf-8", "cp1254", "iso-8859-9")


def read_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


class TextDocument(Document):
    extensions = (".txt", ".md")

    def read(self) -> list[Segment]:
        self.content, self.encoding = read_text(self.path)
        self.lines = self.content.splitlines(keepends=True)
        segs = []
        for i, line in enumerate(self.lines, 1):
            body = line.rstrip("\r\n")
            segs.append(Segment(body, f"satır {i}"))
        return segs

    def save(self, out: Path, replacer) -> None:
        parts = []
        for line, seg in zip(self.lines, self.segments):
            body = line.rstrip("\r\n")
            ending = line[len(body):]
            parts.append(replacer.apply(body, seg) + ending)
        out.write_bytes("".join(parts).encode(self.encoding))
