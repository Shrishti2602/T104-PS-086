
from pathlib import Path

import pytest

from quality_engine.data_loader import (
    load_lot_size_bands,
    load_sampling_table,
)
from quality_engine.sampling import plan_sampling


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

BANDS = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")
RULES = load_sampling_table(DATA_DIR / "sampling_table.csv")


def make_plan(lot_size, severity="NORMAL"):
    return plan_sampling(
        lot_size=lot_size,
        aql_critical="0.065",
        aql_major="1.0",
        aql_minor="2.5",
        severity=severity,
        bands=BANDS,
        rules=RULES,
    )


def test_lot_size_280_uses_code_g():
    assert make_plan(280).code_letter == "G"


def test_lot_size_281_uses_code_h():
    assert make_plan(281).code_letter == "H"


def test_all_three_aql_rules_are_selected():
    plan = make_plan(280)
    assert plan.critical_rule.aql == "0.065"
    assert plan.major_rule.aql == "1.0"
    assert plan.minor_rule.aql == "2.5"


def test_small_lot_uses_full_inspection():
    plan = make_plan(8)
    assert plan.full_inspection is True
    assert plan.n_critical == 8
    assert plan.n_major == 8
    assert plan.n_minor == 8


def test_sample_sizes_match_selected_rules_when_not_full_inspection():
    plan = make_plan(280)
    if plan.full_inspection:
        assert plan.n_critical == 280
        assert plan.n_major == 280
        assert plan.n_minor == 280
    else:
        assert plan.n_critical == plan.critical_rule.sample_size
        assert plan.n_major == plan.major_rule.sample_size
        assert plan.n_minor == plan.minor_rule.sample_size


def test_tightened_severity_is_supported():
    assert make_plan(280, "TIGHTENED").severity == "TIGHTENED"


def test_invalid_severity_is_rejected():
    with pytest.raises(ValueError):
        make_plan(280, "INVALID")


def test_sample_equal_to_lot_size_uses_full_inspection():
    plan = make_plan(200)
    assert plan.full_inspection is True
    assert plan.n_critical == 200
    assert plan.n_major == 200
    assert plan.n_minor == 200


def test_sample_larger_than_lot_size_uses_full_inspection():
    plan = make_plan(199)
    assert plan.full_inspection is True
    assert plan.n_critical == 199
    assert plan.n_major == 199
    assert plan.n_minor == 199


def test_full_inspection_preserves_original_ac_re_limits():
    plan = make_plan(8)

    assert plan.full_inspection is True
    assert plan.critical_rule.ac == 0
    assert plan.critical_rule.re == 1
    assert plan.major_rule.ac == 0
    assert plan.major_rule.re == 1
    assert plan.minor_rule.ac == 0
    assert plan.minor_rule.re == 1
