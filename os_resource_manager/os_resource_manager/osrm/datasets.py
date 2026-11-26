"""Loading the shared JSON datasets in data/."""

import json
from pathlib import Path

from .logger import PROJECT_ROOT, get_logger
from .validation import ValidationError

log = get_logger("datasets")
DATA_DIR = PROJECT_ROOT / "data"


def load(name):
    """Load data/<name>.json (or a full path) and return the parsed dict."""
    path = Path(name)
    if not path.suffix:
        path = DATA_DIR / f"{name}.json"
    if not path.exists():
        raise ValidationError(f"Dataset file not found: {path}")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path.name} is not valid JSON (line {exc.lineno}): {exc.msg}") from None
    if not isinstance(data, dict):
        raise ValidationError(f"{path.name} must contain a JSON object")
    log.info("Loaded dataset %s", path.name)
    return data
