"""Input validation used by every module.

All checks raise ValidationError with a message that says exactly what is wrong,
so the menu can show it to the user and the log can record it.
"""


class ValidationError(ValueError):
    """Raised when input data is missing, malformed or out of range."""


def require_int(value, name, minimum=None, maximum=None):
    """Return value as an int, or raise ValidationError."""
    if isinstance(value, bool):
        raise ValidationError(f"{name} must be a whole number, got {value!r}")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a whole number, got {value!r}") from None
    if isinstance(value, float) and value != number:
        raise ValidationError(f"{name} must be a whole number, got {value!r}")
    if minimum is not None and number < minimum:
        raise ValidationError(f"{name} must be at least {minimum}, got {number}")
    if maximum is not None and number > maximum:
        raise ValidationError(f"{name} must be at most {maximum}, got {number}")
    return number


def parse_int_list(text, name, minimum=None, maximum=None, allow_empty=False):
    """Turn '1 2 3' or '1,2,3' into [1, 2, 3], validating every number."""
    if text is None:
        raise ValidationError(f"{name} is missing")
    parts = str(text).replace(",", " ").split()
    if not parts and not allow_empty:
        raise ValidationError(f"{name} cannot be empty")
    return [require_int(p, f"{name} value", minimum, maximum) for p in parts]


def require_list(values, name, min_length=1):
    if not isinstance(values, (list, tuple)):
        raise ValidationError(f"{name} must be a list")
    if len(values) < min_length:
        raise ValidationError(f"{name} needs at least {min_length} item(s), got {len(values)}")
    return list(values)


def require_matrix(matrix, name, rows, cols, minimum=0):
    """Check a rows x cols matrix of non-negative whole numbers."""
    matrix = require_list(matrix, name, 1)
    if len(matrix) != rows:
        raise ValidationError(f"{name} must have {rows} rows (one per process), got {len(matrix)}")
    clean = []
    for i, row in enumerate(matrix):
        row = require_list(row, f"{name} row {i}", 1)
        if len(row) != cols:
            raise ValidationError(f"{name} row {i} must have {cols} values (one per resource), got {len(row)}")
        clean.append([require_int(v, f"{name}[{i}]", minimum) for v in row])
    return clean
