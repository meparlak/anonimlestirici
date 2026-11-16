"""Windows uygulamasının giriş noktası (PyInstaller)."""

import sys

from anonimlestirici.desktop.app import main

if __name__ == "__main__":
    sys.exit(main())
