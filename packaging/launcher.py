"""Paketlenmiş motorun giriş noktası."""

import mimetypes
import sys

# Sandbox içinde /etc altındaki sistem dosyaları okunamaz; mimetypes bunları aramasın.
mimetypes.knownfiles = []

from anonimlestirici.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
