"""Windows (ve diğer masaüstü) sürümünün kullanıcı tercihleri.

Alan adları Mac sürümündeki Preferences ile aynıdır; böylece iki arayüz motoru aynı şekilde
yapılandırır. Dosya: %APPDATA%\\Anonimlestirici\\tercihler.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..core.settings import DEFAULT_ENABLED, DEFAULT_HEADERS, app_support_dir
from ..core.types import EntityType

DEFAULTS: dict = {
    "enabled": {},
    "tcChecksum": True,
    "nameAliases": True,
    "nerEnabled": True,
    "customTerms": [],
    "excludeTerms": [],
    "headers": None,  # None: motorun varsayılanları
    "codeFormat": "bracket",
    "outputSuffix": "_anonim",
    "cleanMetadata": True,
    "askOutputFolder": True,
    "outputFolder": "",
    "recent": [],
}


def path() -> Path:
    return app_support_dir() / "tercihler.json"


def load() -> dict:
    prefs = json.loads(json.dumps(DEFAULTS))
    try:
        data = json.loads(path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            prefs.update({k: v for k, v in data.items() if k in DEFAULTS})
    except (OSError, json.JSONDecodeError):
        pass
    return prefs


def save(prefs: dict) -> None:
    clean = {k: prefs.get(k, v) for k, v in DEFAULTS.items()}
    path().write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")


def is_enabled(prefs: dict, et: EntityType) -> bool:
    return bool(prefs.get("enabled", {}).get(et.value, DEFAULT_ENABLED[et]))


def engine_settings(prefs: dict) -> dict:
    """Motorun beklediği Settings alanları (Mac sürümündeki engineSettings ile aynı)."""
    return {
        "enabled": {et.value: is_enabled(prefs, et) for et in EntityType},
        "tc_checksum": bool(prefs.get("tcChecksum", True)),
        "name_aliases": bool(prefs.get("nameAliases", True)),
        "ner_enabled": bool(prefs.get("nerEnabled", True)),
        "custom_terms": list(prefs.get("customTerms") or []),
        "exclude_terms": list(prefs.get("excludeTerms") or []),
        "code_format": prefs.get("codeFormat") or "bracket",
        "output_suffix": prefs.get("outputSuffix") or "_anonim",
        "clean_metadata": bool(prefs.get("cleanMetadata", True)),
        "headers": prefs.get("headers") or dict(DEFAULT_HEADERS),
        # Windows sürümünde ağ bağlantısı yok; yerel LLM özelliği bulunmaz.
        "llm": {"enabled": False},
    }


def add_recent(prefs: dict, name: str, file_path: str, found: int) -> None:
    item = {"name": name, "path": file_path, "when": datetime.now().strftime("%d.%m.%Y %H:%M"), "found": found}
    prefs["recent"] = ([item] + list(prefs.get("recent") or []))[:8]
