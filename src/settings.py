# settings.py
#
# Persistent user settings. Stored as JSON under data/ next to the repo root.

import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR  = os.path.join(_REPO_ROOT, "data")
CONFIG_PATH = os.path.join(_DATA_DIR, "settings.json")

DEFAULTS = {
    "appearance": "system",
    "language": "en",
    "library_root": os.path.join(_REPO_ROOT, "library"),
    "auto_detect_on_startup": True,
    "double_read_on_dump": True,
    "verify_after_flash": True,
    "backup_before_flash": True,
    "fast_mode": True,
}


class Settings:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self._data = dict(DEFAULTS)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._load()

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in DEFAULTS:
                    if k in data:
                        self._data[k] = data[k]
        except (FileNotFoundError, ValueError, OSError):
            pass

    def save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)