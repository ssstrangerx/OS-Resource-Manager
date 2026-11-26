"""Activity logging shared by every module (and by the Bash scripts, which append to the same file)."""

import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "activity.log"

_configured = False


def get_logger(name):
    """Return a logger that writes timestamped lines to logs/activity.log."""
    global _configured
    if not _configured:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)-15s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"))
        root = logging.getLogger("osrm")
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        root.propagate = False
        _configured = True
    return logging.getLogger(f"osrm.{name}")


def tail(lines=20):
    """Return the last `lines` lines of the activity log."""
    if not LOG_FILE.exists():
        return "(log is empty)"
    with open(LOG_FILE, encoding="utf-8") as f:
        content = f.readlines()
    return "".join(content[-lines:]) or "(log is empty)"
