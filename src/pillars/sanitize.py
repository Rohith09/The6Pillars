import re
from typing import Any

REDACTED_VALUE = "[REDACTED]"

_SAFE_KEY_PATTERNS = (
    ("public", "key"),
    ("key", "name"),
    ("secret", "name"),
    ("secret", "id"),
    ("secret", "arn"),
    ("secret", "version"),
)

_SENSITIVE_KEY_PATTERNS = (
    ("api", "key"),
    ("access", "key"),
    ("secret", "key"),
    ("private", "key"),
    ("client", "secret"),
    ("connection", "string"),
    ("user", "data"),
)

_SENSITIVE_TOKENS = {"password", "passwd", "secret", "token", "authorization"}
_SENSITIVE_COMPACT_SUFFIXES = {
    "apikey",
    "accesskey",
    "secretkey",
    "privatekey",
    "clientsecret",
    "connectionstring",
    "userdata",
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
}


def _split_key(key: str) -> tuple[list[str], str]:
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", key)
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", spaced)
    tokens = re.findall(r"[a-z0-9]+", spaced.lower())
    compact = "".join(tokens)
    return tokens, compact


def _has_sequence(tokens: list[str], pattern: tuple[str, ...]) -> bool:
    if len(tokens) < len(pattern):
        return False
    return any(
        tuple(tokens[i : i + len(pattern)]) == pattern
        for i in range(len(tokens) - len(pattern) + 1)
    )


def _ends_with_sequence(tokens: list[str], pattern: tuple[str, ...]) -> bool:
    return len(tokens) >= len(pattern) and tuple(tokens[-len(pattern) :]) == pattern


def _is_safe_identifier(tokens: list[str], compact: str) -> bool:
    return any(
        compact == "".join(pattern) or _ends_with_sequence(tokens, pattern)
        for pattern in _SAFE_KEY_PATTERNS
    )


def is_sensitive_key(key: str) -> bool:
    """Return True when a Terraform attribute key probably carries secret material."""
    tokens, compact = _split_key(key)
    if not tokens or _is_safe_identifier(tokens, compact):
        return False

    if any(token in _SENSITIVE_TOKENS for token in tokens):
        return True
    if any(_has_sequence(tokens, pattern) for pattern in _SENSITIVE_KEY_PATTERNS):
        return True
    return any(compact.endswith(suffix) for suffix in _SENSITIVE_COMPACT_SUFFIXES)


def _redact_all(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_all(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_all(child) for child in value]
    return REDACTED_VALUE


def sanitize_value(value: Any, sensitivity: Any = None) -> Any:
    """Return a sanitized copy using Terraform sensitivity metadata and key fallback."""
    if sensitivity is True:
        return _redact_all(value)

    if isinstance(value, dict):
        sensitivity_by_key = sensitivity if isinstance(sensitivity, dict) else {}
        return {
            key: _redact_all(child)
            if is_sensitive_key(str(key))
            else sanitize_value(child, sensitivity_by_key.get(key))
            for key, child in value.items()
        }

    if isinstance(value, list):
        sensitivity_by_index = sensitivity if isinstance(sensitivity, list) else []
        return [
            sanitize_value(
                child,
                sensitivity_by_index[index]
                if index < len(sensitivity_by_index)
                else None,
            )
            for index, child in enumerate(value)
        ]

    return value


def sanitize_after(after: dict | None, after_sensitive: Any = None) -> dict | None:
    """Sanitize Terraform change.after while preserving ResourceChange.after's shape."""
    if after is None:
        return None
    if not isinstance(after, dict):
        return None

    sanitized = sanitize_value(after, after_sensitive)
    return sanitized if isinstance(sanitized, dict) else None
