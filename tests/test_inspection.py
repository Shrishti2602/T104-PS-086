
from pathlib import Path

import pytest

from quality_engine.data_loader import load_sampling_table
from quality_engine.inspection import evaluate_inspection


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES = load_sampling_table(
    PROJECT_ROOT / "data" / "sampling_table.csv"
)

CRITICAL = RULES[("A", "0.065", "NORMAL")]
MAJOR = RULES[("A", "1.0", "NORMAL")]
MINOR = RULES[("A", "2.5", "NORMAL")]


def evaluate(c=0, m=0, n=0):
    return evaluate_inspection(
        c, m, n, CRITICAL, MAJOR, MINOR
    )


def test_zero_defects_are_accepted():
    assert evaluate().decision == "ACCEPT"


def test_critical_defect_reaching_re_rejects():
    result = evaluate(c=CRITICAL.re)
    assert result.decision == "REJECT"


def test_major_defect_reaching_re_rejects():
    result = evaluate(m=MAJOR.re)
    assert result.decision == "REJECT"


def test_minor_defect_reaching_re_rejects():
    result = evaluate(n=MINOR.re)
    assert result.decision == "REJECT"


def test_exactly_ac_is_accepted():
    result = evaluate(
        c=CRITICAL.ac,
        m=MAJOR.ac,
        n=MINOR.ac,
    )
    assert result.decision == "ACCEPT"


def test_negative_defect_count_is_invalid():
    with pytest.raises(ValueError):
        evaluate(c=-1)


def test_fractional_defect_count_is_invalid():
    with pytest.raises(ValueError):
        evaluate(m=1.5)


def test_critical_defect_always_rejects():
    result = evaluate(c=1)
    assert result.decision == "REJECT"


def test_rejection_reason_identifies_defect_class():
    result = evaluate(m=MAJOR.re)
    assert "major" in result.reason
