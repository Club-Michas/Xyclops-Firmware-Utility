# lang.py
#
# Tiny localization helper. Language files live in lang/<code>.json.

import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG_DIR = os.path.join(_REPO_ROOT, "lang")
FALLBACK = "en"


class Lang:
    def __init__(self, folder=LANG_DIR):
        self.folder = folder
        self.code = FALLBACK
        self._strings = {}
        self._fallback = {}
        os.makedirs(self.folder, exist_ok=True)
        self._load_folder()
        self.set_language(FALLBACK)

    def _load_folder(self):
        self._available = {}
        if not os.path.isdir(self.folder):
            return
        for name in sorted(os.listdir(self.folder)):
            if not name.endswith(".json"):
                continue
            code = name[:-5]
            path = os.path.join(self.folder, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._available[code] = data
            except (ValueError, OSError):
                continue

    def reload(self):
        self._load_folder()
        if self.code not in self._available:
            self.code = FALLBACK
        self.set_language(self.code)

    def available(self):
        out = []
        for code, data in self._available.items():
            name = data.get("__name__", code)
            out.append((code, name))
        out.sort(key=lambda p: p[1].lower())
        return out

    def set_language(self, code):
        self.code = code if code in self._available else FALLBACK
        self._strings = self._available.get(self.code, {})
        self._fallback = self._available.get(FALLBACK, {})

    def __call__(self, key, **fmt):
        text = self._strings.get(key)
        if text is None:
            text = self._fallback.get(key, key)
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError):
                return text
        return text