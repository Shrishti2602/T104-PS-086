from pathlib import Path

import pytest

from quality_engine.data_loader import (
    load_sampling_table,
    SamplingRule,
)
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
    assert evaluate(c=CRITICAL.re).decision == "REJECT"


def test_major_defect_reaching_re_rejects():
    assert evaluate(m=MAJOR.re).decision == "REJECT"


def test_minor_defect_reaching_re_rejects():
    assert evaluate(n=MINOR.re).decision == "REJECT"


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
    assert evaluate(c=1).decision == "REJECT"


def test_rejection_reason_identifies_defect_class():
    result = evaluate(m=MAJOR.re)
    assert "major" in result.reason


def test_single_critical_defect_rejects_even_when_re_is_greater_than_one():
    critical_rule = SamplingRule(
        code_letter="A",
        aql="0.065",
        severity="NORMAL",
        sample_size=5,
        ac=0,
        re=2,
        reduced_limit=0,
    )

    result = evaluate_inspection(
        critical=1,
        major=0,
        minor=0,
        critical_rule=critical_rule,
        major_rule=MAJOR,
        minor_rule=MINOR,
    )

    assert result.decision == "REJECT"
