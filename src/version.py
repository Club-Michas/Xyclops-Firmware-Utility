# version.py
#
# Single source of truth for application metadata.
# Bump VERSION here when you release; everything else reads from this file.

APP_NAME    = "Xyclops Firmware Utility"
APP_SHORT   = "XFU"
VERSION     = "1.0.0"
AUTHOR      = "Michael Rozwadowski (@Club-Michas)"
AUTHOR_URL  = "https://github.com/Club-Michas"
PROJECT_URL = "https://github.com/Club-Michas/Xyclops-Firmware-Utility"
LICENSE     = "MIT"

PROTOCOL_CREDIT_NAME = "Prehistoricman"
PROTOCOL_CREDIT_URL  = "https://github.com/Prehistoricman/Xbox_SMC"
PROTOCOL_CREDIT_TEXT = (
    "The Xyclops serial protocol used by this tool was reverse-engineered "
    "by Prehistoricman and is documented in the Xbox_SMC project. Command "
    "framing, address layout, and BIOS/SMC read/write/erase behavior in "
    "this tool are all derived from that work."
)

THIRD_PARTY = [
    ("pyserial", "https://github.com/pyserial/pyserial"),
    ("sv-ttk", "https://github.com/rdbende/Sun-Valley-ttk-theme"),
]


def version_string():
    return f"{APP_NAME} v{VERSION}"


def version_short():
    return f"{APP_SHORT} v{VERSION}"