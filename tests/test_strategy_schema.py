# tests/test_strategy_schema.py
import pytest
from engine.strategy_schema import validate_profile, ValidationError
from engine.recommended_config import RECOMMENDED


def test_recommended_validates():
    # Recommended itself must pass validation
    validate_profile(RECOMMENDED)


def test_missing_section_rejected():
    bad = {k: v for k, v in RECOMMENDED.items() if k != "entry_gates"}
    with pytest.raises(ValidationError, match="entry_gates"):
        validate_profile(bad)


def test_adx_out_of_bounds_rejected():
    import copy
    bad = copy.deepcopy(RECOMMENDED)
    bad["entry_gates"]["adx_min"] = 999
    with pytest.raises(ValidationError, match="adx_min"):
        validate_profile(bad)


def test_negative_position_size_rejected():
    import copy
    bad = copy.deepcopy(RECOMMENDED)
    bad["position"]["allocation_usd"] = -100
    with pytest.raises(ValidationError, match="allocation_usd"):
        validate_profile(bad)


def test_blacklist_must_be_list_of_strings():
    import copy
    bad = copy.deepcopy(RECOMMENDED)
    bad["universe"]["blacklist"] = "AERO-USD"  # string, not list
    with pytest.raises(ValidationError, match="blacklist"):
        validate_profile(bad)


def test_trail_progressive_must_be_pair_list():
    import copy
    bad = copy.deepcopy(RECOMMENDED)
    bad["trail"]["progressive"] = [[1.0]]  # missing trail_pct
    with pytest.raises(ValidationError, match="progressive"):
        validate_profile(bad)


def test_weekday_block_validates_0_to_6():
    import copy
    bad = copy.deepcopy(RECOMMENDED)
    bad["entry_pause"]["weekday_block"] = [7]
    with pytest.raises(ValidationError, match="weekday"):
        validate_profile(bad)
