"""Regression test for the strategy_profiles.json path resolver.

Pre-fix: DEFAULT_FILE_PATH was hardcoded to 'data/strategy_profiles.json',
a path inside the container image (not on a mount). When CasaOS recreated
the container (e.g., on env-var save), this file was reset to whatever
the Docker image carried, silently wiping the user's saved profiles.

Now: _resolve_default_path() uses /app/persistent if that dir exists
(production), else falls back to the repo-relative dev path.
"""
import os
from unittest.mock import patch


def test_resolver_uses_persistent_when_dir_exists():
    from engine.strategy_profiles import _resolve_default_path
    with patch("os.path.isdir") as m:
        m.return_value = True
        assert _resolve_default_path() == "/app/persistent/strategy_profiles.json"
        m.assert_called_with("/app/persistent")


def test_resolver_falls_back_to_repo_path_when_no_persistent():
    from engine.strategy_profiles import _resolve_default_path
    with patch("os.path.isdir") as m:
        m.return_value = False
        assert _resolve_default_path() == "data/strategy_profiles.json"
