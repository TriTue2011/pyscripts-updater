"""Utility helpers for Pyscript Updater."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

from .const import (
    ALLOWED_HOSTS,
    CONF_MAX_BACKUPS,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_BACKUPS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    MAX_BACKUPS,
    MAX_UPDATE_INTERVAL_HOURS,
    MIN_BACKUPS,
    MIN_UPDATE_INTERVAL,
)


def _get_option(config: Any, key: str, default: Any) -> Any:
    if config is None:
        return default
    if hasattr(config, "options"):
        return config.options.get(key, config.data.get(key, default))
    if isinstance(config, dict):
        return config.get(key, default)
    return default


def get_config_int(
    config: Any,
    key: str,
    default: int,
    min_val: int | None = None,
    max_val: int | None = None,
) -> int:
    """Get an int option clamped to [min_val, max_val]."""
    val = _get_option(config, key, default)
    try:
        result = int(float(str(val).strip()))
    except (ValueError, TypeError, OverflowError):
        return default
    if min_val is not None:
        result = max(min_val, result)
    if max_val is not None:
        result = min(max_val, result)
    return result


def get_update_interval(config: Any) -> int:
    """Return update interval (hours), clamped."""
    return get_config_int(
        config,
        CONF_UPDATE_INTERVAL,
        DEFAULT_UPDATE_INTERVAL_HOURS,
        min_val=MIN_UPDATE_INTERVAL,
        max_val=MAX_UPDATE_INTERVAL_HOURS,
    )


def get_max_backups(config: Any) -> int:
    """Return max backups, clamped."""
    return get_config_int(
        config,
        CONF_MAX_BACKUPS,
        DEFAULT_MAX_BACKUPS,
        min_val=MIN_BACKUPS,
        max_val=MAX_BACKUPS,
    )


def get_option(config: Any, key: str, default: Any) -> Any:
    """Public wrapper to read an option from a ConfigEntry or dict."""
    return _get_option(config, key, default)


def is_allowed_url(url: str) -> bool:
    """Return True only for https URLs on a GitHub host (the sole place files and token may go)."""
    parts = urlsplit(url)
    return parts.scheme == "https" and (parts.hostname or "").lower() in ALLOWED_HOSTS


def safe_join(base: str, rel_path: str) -> str:
    """Join ``rel_path`` under ``base``; raise ValueError if it would leave ``base``."""
    if os.path.isabs(rel_path):
        raise ValueError(f"absolute path not allowed: {rel_path}")
    root = os.path.realpath(base)
    full = os.path.realpath(os.path.join(root, rel_path))
    if full != root and not full.startswith(root + os.sep):
        raise ValueError(f"path escapes pyscript dir: {rel_path}")
    return full
