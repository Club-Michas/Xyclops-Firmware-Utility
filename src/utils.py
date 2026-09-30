# utils.py

import os
import math
import hashlib
from datetime import datetime

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKUPS_DIR = os.path.join(_REPO_ROOT, "output", "backups")


def pad_to_64(data: bytes):
    padding = (math.ceil(len(data) / 64) * 64) - len(data)
    if padding > 0:
        return data + (b"\xFF" * padding)
    return data


def md5(data: bytes):
    return hashlib.md5(data).hexdigest()


def sha1(data: bytes):
    return hashlib.sha1(data).hexdigest()


def sha256(data: bytes):
    return hashlib.sha256(data).hexdigest()


def hex_list(data: bytes):
    return " ".join(f"{b:02X}" for b in data)


def make_backup_folder(base=None):
    if base is None:
        base = _BACKUPS_DIR
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    folder = os.path.join(base, ts)
    os.makedirs(folder, exist_ok=True)
    return folder


def save_file(path, data: bytes):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def timestamped_path(folder, prefix, ext=".bin"):
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, f"{prefix}_{ts}{ext}")


def format_digests(data: bytes):
    return (
        f"Size:   {len(data)} bytes (0x{len(data):X})\n"
        f"MD5:    {md5(data)}\n"
        f"SHA1:   {sha1(data)}\n"
        f"SHA256: {sha256(data)}"
    )