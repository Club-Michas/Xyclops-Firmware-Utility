# firmware_library.py
#
# Manages the folder of BIOS/SMC files and remembers the last-used folder.

import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR  = os.path.join(_REPO_ROOT, "data")
CONFIG_PATH = os.path.join(_DATA_DIR, "firmware_library.json")
DEFAULT_ROOT = os.path.join(_REPO_ROOT, "library")

BIOS_EXTS = (".bin", ".rom", ".bios")
SMC_EXTS  = (".bin", ".smc")


class FirmwareLibrary:
    def __init__(self, config_path=CONFIG_PATH):
        self.config_path = config_path
        self.root = DEFAULT_ROOT
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        self._load()

    def _load(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            root = data.get("root")
            if root:
                self.root = root
        except (FileNotFoundError, ValueError, OSError):
            pass

    def _save(self):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump({"root": self.root}, f, indent=2)
        except OSError:
            pass

    def set_root(self, folder):
        self.root = folder
        self._save()

    def list_files(self, kind):
        exts = BIOS_EXTS if kind == "bios" else SMC_EXTS
        subdir = os.path.join(self.root, kind)
        candidates = [subdir, self.root]
        out = []
        for base in candidates:
            if not os.path.isdir(base):
                continue
            try:
                for name in sorted(os.listdir(base)):
                    full = os.path.join(base, name)
                    if not os.path.isfile(full):
                        continue
                    if name.lower().endswith(exts):
                        out.append(full)
            except OSError:
                pass
            if out:
                break
        return out