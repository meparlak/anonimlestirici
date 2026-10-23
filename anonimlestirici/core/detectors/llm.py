"""Yerel LLM (Ollama) ile ikinci kontrol. Deneysel, varsayılan olarak kapalı.

Yalnızca kullanıcının kendi bilgisayarındaki Ollama sunucusuna bağlanır. Model yalnızca
öneri üretir; öneriler önizlemede "LLM" kaynağıyla görünür ve kullanıcı onayı bekler.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from ..textutil import bounded, ci_pattern
from ..types import EntityType, Finding, Segment
from .base import Detector

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}

PROMPT = """Aşağıdaki Türkçe metinde geçen kişisel verileri bul.
Türler: KİŞİ (ad, soyad), TC, TELEFON, EPOSTA, ADRES, BİRİM (departman), KURUM (şirket, kurum).
Yalnızca metinde birebir geçen ifadeleri yaz. Emin değilsen yazma.
Cevabı yalnızca şu JSON biçiminde ver: {"bulgular": [{"metin": "...", "tur": "KİŞİ"}]}

Metin:
"""


def is_local(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in LOCAL_HOSTS


def _post(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (yalnızca yerel adres)
        return json.loads(resp.read().decode("utf-8"))


def list_models(url: str, timeout: int = 5) -> list[str]:
    """Ollama'da yüklü modelleri döndürür; bağlanamazsa hata fırlatır."""
    req = urllib.request.Request(url.rstrip("/") + "/api/tags")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        data = json.loads(resp.read().decode("utf-8"))
    return [m.get("name", "") for m in data.get("models", [])]


class OllamaDetector(Detector):
    name = "LLM"
    types = (EntityType.KISI, EntityType.ADRES, EntityType.BIRIM, EntityType.KURUM)

    def __init__(self, settings, transport=None):
        super().__init__(settings)
        self.cfg = settings.llm
        self._post = transport or _post
        self.errors = 0

    @property
    def active(self) -> bool:
        if not self.cfg.enabled or not super().active:
            return False
        return is_local(self.cfg.url) or self.cfg.allow_remote

    def detect(self, segment: Segment) -> list[Finding]:
        text = segment.text
        if len(text.strip()) < self.cfg.min_chars or self.errors >= 3:
            return []
        payload = {
            "model": self.cfg.model,
            "prompt": PROMPT + text,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
        }
        try:
            data = self._post(self.cfg.url.rstrip("/") + "/api/generate", payload, self.cfg.timeout)
            items = json.loads(data.get("response", "{}")).get("bulgular", [])
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, AttributeError):
            self.errors += 1
            return []
        out: list[Finding] = []
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict):
                continue
            value = str(item.get("metin", "")).strip()
            try:
                et = EntityType.parse(str(item.get("tur", "")))
            except ValueError:
                continue
            if len(value) < 2 or not self.settings.is_enabled(et):
                continue
            # Model metinde olmayan bir şey uydurduysa yok say.
            for m in re.finditer(bounded(ci_pattern(value)), text):
                out.append(Finding(m.start(), m.end(), m.group(), et, 0.45, self.name))
        return out
