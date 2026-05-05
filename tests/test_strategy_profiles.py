# tests/test_strategy_profiles.py
import json
import os
import tempfile

import pytest

from engine.strategy_profiles import (
    load_strategy_profiles,
    save_strategy_profiles,
    save_user_profile,
    delete_user_profile,
    set_active_profile,
    get_active_profile_values,
    DEFAULT_FILE_PATH,
)
from engine.recommended_config import RECOMMENDED


def _temp_path():
    return os.path.join(tempfile.mkdtemp(), "strategy_profiles.json")


def test_load_returns_default_state_when_file_missing():
    path = _temp_path()
    state = load_strategy_profiles(path)
    assert state["active"] == "builtin::recommended"
    assert state["user_profiles"] == {}
    assert state["applied_recommended_version"] is None


def test_save_and_reload_round_trip():
    path = _temp_path()
    state = {"active": "builtin::aggressive", "applied_recommended_version": "2.0",
             "user_profiles": {"foo": {"created_at": "2026-05-01", "updated_at": "2026-05-01",
                                       "description": "test", "values": RECOMMENDED}}}
    save_strategy_profiles(path, state)
    again = load_strategy_profiles(path)
    assert again["active"] == "builtin::aggressive"
    assert "foo" in again["user_profiles"]


def test_save_user_profile_creates_entry():
    path = _temp_path()
    save_user_profile(path, "my-fav", "first save", RECOMMENDED)
    state = load_strategy_profiles(path)
    assert "my-fav" in state["user_profiles"]
    assert state["user_profiles"]["my-fav"]["description"] == "first save"


def test_save_user_profile_rejects_builtin_collision():
    path = _temp_path()
    with pytest.raises(ValueError, match="builtin"):
        save_user_profile(path, "Recommended", "x", RECOMMENDED)


def test_delete_user_profile_removes_entry():
    path = _temp_path()
    save_user_profile(path, "my-fav", "first", RECOMMENDED)
    delete_user_profile(path, "my-fav")
    state = load_strategy_profiles(path)
    assert "my-fav" not in state["user_profiles"]


def test_delete_active_falls_back_to_recommended():
    path = _temp_path()
    save_user_profile(path, "my-fav", "first", RECOMMENDED)
    set_active_profile(path, "user::my-fav")
    delete_user_profile(path, "my-fav")
    state = load_strategy_profiles(path)
    assert state["active"] == "builtin::recommended"


def test_get_active_values_returns_builtin():
    path = _temp_path()
    set_active_profile(path, "builtin::aggressive")
    values = get_active_profile_values(path)
    assert values["entry_gates"]["ath_dist_max"] == -8  # AGGRESSIVE value


def test_get_active_values_returns_user_profile():
    path = _temp_path()
    custom = {**RECOMMENDED, "entry_gates": {**RECOMMENDED["entry_gates"], "adx_min": 99}}
    save_user_profile(path, "test", "x", custom)
    set_active_profile(path, "user::test")
    values = get_active_profile_values(path)
    assert values["entry_gates"]["adx_min"] == 99


def test_atomic_write_does_not_leave_tmp():
    path = _temp_path()
    save_user_profile(path, "test", "x", RECOMMENDED)
    tmp = path + ".tmp"
    assert not os.path.exists(tmp)
