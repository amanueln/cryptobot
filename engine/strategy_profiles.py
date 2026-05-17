# engine/strategy_profiles.py
"""User-saved strategy profile I/O.

State file: data/strategy_profiles.json
Schema:
{
  "active": "builtin::recommended" | "builtin::conservative" | "builtin::aggressive" | "user::<name>",
  "applied_recommended_version": "2.0" | null,
  "user_profiles": {
    "<name>": { "created_at": ISO, "updated_at": ISO, "description": str, "values": dict }
  }
}

All writes are atomic (tmp + os.replace). Built-in profiles live in
engine/recommended_config.py and are not persisted here.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional

from engine.recommended_config import BUILTIN_PROFILES
from engine.strategy_schema import validate_profile


def _resolve_default_path() -> str:
    """Pick a persistent path for the profile state file.

    In production the container has /app/persistent mounted from the host;
    state written there survives container recreation (including CasaOS
    Save+restart, which RECREATES the container and wipes anything inside
    /app/src that isn't symlinked). For local dev (no /app/persistent),
    fall back to the repo-relative path.

    History: 2026-05-17 a CasaOS env-var change recreated the container and
    silently wiped 8.9KB of user profile state because this file was at
    /app/src/data/strategy_profiles.json — inside the image, not on a
    mount. Don't let that happen again.
    """
    if os.path.isdir("/app/persistent"):
        return "/app/persistent/strategy_profiles.json"
    return "data/strategy_profiles.json"


DEFAULT_FILE_PATH = _resolve_default_path()


def _default_state() -> dict:
    return {
        "active": "builtin::recommended",
        "applied_recommended_version": None,
        "user_profiles": {},
    }


def load_strategy_profiles(path: str = DEFAULT_FILE_PATH) -> dict:
    """Load state from disk. Returns default state if file missing."""
    if not os.path.exists(path):
        return _default_state()
    with open(path, "r") as f:
        state = json.load(f)
    # Backfill missing keys
    for k, v in _default_state().items():
        state.setdefault(k, v)
    return state


def save_strategy_profiles(path: str, state: dict) -> None:
    """Write state atomically (tmp + replace)."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_user_profile(path: str, name: str, description: str, values: dict) -> None:
    """Create or update a user profile. Validates values first.

    Raises ValueError if name collides with a builtin (case-insensitive match).
    """
    if not name or not name.strip():
        raise ValueError("profile name is required")
    if name.lower() in {k.lower() for k in BUILTIN_PROFILES}:
        raise ValueError(f"name {name!r} collides with a builtin — pick another")
    validate_profile(values)
    state = load_strategy_profiles(path)
    existing = state["user_profiles"].get(name)
    state["user_profiles"][name] = {
        "created_at": existing["created_at"] if existing else _now(),
        "updated_at": _now(),
        "description": description,
        "values": values,
    }
    save_strategy_profiles(path, state)


def delete_user_profile(path: str, name: str) -> None:
    """Delete a user profile. If active, falls back to builtin::recommended."""
    state = load_strategy_profiles(path)
    if name not in state["user_profiles"]:
        return
    state["user_profiles"].pop(name)
    if state["active"] == f"user::{name}":
        state["active"] = "builtin::recommended"
    save_strategy_profiles(path, state)


def set_active_profile(path: str, key: str) -> None:
    """Set the active profile by namespaced key (builtin::X or user::X)."""
    state = load_strategy_profiles(path)
    state["active"] = key
    save_strategy_profiles(path, state)


def get_active_profile_values(path: str = DEFAULT_FILE_PATH) -> dict:
    """Return the values dict for whichever profile is currently active."""
    state = load_strategy_profiles(path)
    key = state["active"]
    if key.startswith("builtin::"):
        name = key.split("::", 1)[1]
        if name not in BUILTIN_PROFILES:
            raise KeyError(f"builtin profile {name!r} not found")
        return BUILTIN_PROFILES[name]
    if key.startswith("user::"):
        name = key.split("::", 1)[1]
        prof = state["user_profiles"].get(name)
        if not prof:
            raise KeyError(f"user profile {name!r} not found")
        return prof["values"]
    raise KeyError(f"unknown profile key: {key!r}")
