"""CSV: ayırıcı ve karakter kodlaması otomatik algılanır, aynı biçimde geri yazılır."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from ..types import Segment
from . import Document
from .text import read_text


def col_letter(idx: int) -> str:
    s = ""
    idx += 1
    while idx:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


class CsvDocument(Document):
    extensions = (".csv",)

    def read(self) -> list[Segment]:
        content, self.encoding = read_text(self.path)
        sample = content[:20000]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
            self.delimiter = dialect.delimiter
            self.quotechar = dialect.quotechar or '"'
        except csv.Error:
            self.delimiter = ";" if sample.count(";") > sample.count(",") else ","
            self.quotechar = '"'
        self.lineterminator = "\r\n" if "\r\n" in sample else "\n"
        self.trailing_newline = content.endswith(("\n", "\r"))
        self.rows = list(csv.reader(io.StringIO(content, newline=""), delimiter=self.delimiter, quotechar=self.quotechar))

        hints = {}
        if self.rows:
            for ci, h in enumerate(self.rows[0]):
                et = self.header_hint(h)
                if et:
                    hints[ci] = et
        self.hints = hints
        start_row = 1 if hints else 0
        segs: list[Segment] = []
        self.cells: list[tuple[int, int]] = []
        for ri, row in enumerate(self.rows):
            for ci, val in enumerate(row):
                hint = hints.get(ci) if ri >= start_row else None
                segs.append(Segment(val, f"{col_letter(ci)}{ri + 1}", hint=hint, whole=True))
                self.cells.append((ri, ci))
        return segs

    def save(self, out: Path, replacer) -> None:
        rows = [list(r) for r in self.rows]
        for (ri, ci), seg in zip(self.cells, self.segments):
            rows[ri][ci] = replacer.apply(rows[ri][ci], seg)
        buf = io.StringIO(newline="")
        w = csv.writer(buf, delimiter=self.delimiter, quotechar=self.quotechar, lineterminator=self.lineterminator)
        w.writerows(rows)
        text = buf.getvalue()
        if not self.trailing_newline and text.endswith(self.lineterminator):
            text = text[: -len(self.lineterminator)]
        out.write_bytes(text.encode(self.encoding))
