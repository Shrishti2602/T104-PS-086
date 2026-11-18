
import pytest

from quality_engine.switching import SourceSwitchingState


DEFECTS_ZERO = {"critical": 0, "major": 0, "minor": 0}
AC_LIMITS = {"critical": 0, "major": 2, "minor": 5}
RE_LIMITS = {"critical": 1, "major": 5, "minor": 10}
REDUCED_LIMITS = {"critical": 0, "major": 1, "minor": 2}


def record(source, batch, decision, defects=None, **kwargs):
    return source.record_inspection(
        batch_id=batch,
        decision=decision,
        defects=defects or DEFECTS_ZERO,
        ac_limits=AC_LIMITS,
        re_limits=RE_LIMITS,
        reduced_limits=REDUCED_LIMITS,
        **kwargs,
    )


def test_initial_state_is_normal():
    source = SourceSwitchingState("SUP-01")
    assert source.state == "NORMAL"


def test_two_rejections_within_five_batches_trigger_tightened():
    source = SourceSwitchingState("SUP-01")
    record(source, "B1", "REJECT")
    record(source, "B2", "ACCEPT")
    event = record(source, "B3", "REJECT")

    assert source.state == "TIGHTENED"
    assert event.to_state == "TIGHTENED"


def test_old_rejection_expires_after_five_batch_window():
    source = SourceSwitchingState("SUP-01")
    record(source, "B1", "REJECT")
    for number in range(2, 6):
        record(source, f"B{number}", "ACCEPT")

    record(source, "B6", "REJECT")
    assert source.state == "NORMAL"


def test_five_consecutive_tightened_acceptances_return_to_normal():
    source = SourceSwitchingState("SUP-01", state="TIGHTENED")

    for number in range(1, 5):
        record(source, f"B{number}", "ACCEPT")

    record(source, "B5", "ACCEPT")
    assert source.state == "NORMAL"


def test_five_tightened_rejections_trigger_discontinued():
    source = SourceSwitchingState("SUP-01", state="TIGHTENED")

    for number in range(1, 5):
        record(source, f"B{number}", "REJECT")

    record(source, "B5", "REJECT")
    assert source.state == "DISCONTINUED"


def test_tightened_rejections_are_cumulative_not_consecutive():
    source = SourceSwitchingState("SUP-01", state="TIGHTENED")

    for number in range(1, 5):
        record(source, f"B{number}", "REJECT")
        record(source, f"A{number}", "ACCEPT")

    record(source, "B5", "REJECT")
    assert source.state == "DISCONTINUED"


def test_corrective_action_resumes_tightened():
    source = SourceSwitchingState("SUP-01", state="DISCONTINUED")

    event = source.corrective_action("CA-01", "CAR-2026-01")

    assert source.state == "TIGHTENED"
    assert event.to_state == "TIGHTENED"


def test_corrective_action_not_allowed_outside_discontinued():
    source = SourceSwitchingState("SUP-01")

    with pytest.raises(ValueError):
        source.corrective_action("CA-01", "CAR-2026-01")


def test_ten_consecutive_acceptances_within_limits_trigger_reduced():
    source = SourceSwitchingState("SUP-01")

    for number in range(1, 10):
        record(source, f"B{number}", "ACCEPT")

    record(source, "B10", "ACCEPT")
    assert source.state == "REDUCED"


def test_rejection_while_reduced_returns_to_normal():
    source = SourceSwitchingState("SUP-01", state="REDUCED")

    record(source, "B1", "REJECT")
    assert source.state == "NORMAL"


def test_between_ac_and_re_while_reduced_returns_to_normal():
    source = SourceSwitchingState("SUP-01", state="REDUCED")

    defects = {"critical": 0, "major": 3, "minor": 0}
    record(source, "B1", "ACCEPT", defects=defects)

    assert source.state == "NORMAL"


def test_late_acceptance_does_not_count_toward_reduced():
    source = SourceSwitchingState("SUP-01")

    for number in range(1, 10):
        record(source, f"B{number}", "ACCEPT")

    record(source, "LATE-01", "ACCEPT", late=True)
    assert source.state == "NORMAL"

    record(source, "B10", "ACCEPT")
    assert source.state == "REDUCED"


def test_production_irregularity_returns_reduced_to_normal():
    source = SourceSwitchingState("SUP-01", state="REDUCED")

    record(
        source,
        "B1",
        "ACCEPT",
        production_irregularity=True,
    )
    assert source.state == "NORMAL"


def test_reinspection_does_not_change_switching_state():
    source = SourceSwitchingState("SUP-01")

    record(
        source,
        "B1",
        "REJECT",
        first_inspection=False,
    )
    assert source.state == "NORMAL"


def test_switching_history_records_transitions():
    source = SourceSwitchingState("SUP-01")

    record(source, "B1", "REJECT")
    record(source, "B2", "REJECT")

    assert len(source.history) == 1
    assert source.history[0].from_state == "NORMAL"
    assert source.history[0].to_state == "TIGHTENED"

def test_second_rejection_on_fifth_batch_boundary_triggers_tightened():
    source = SourceSwitchingState("SUP-01")

    record(source, "B1", "REJECT")
    record(source, "B2", "ACCEPT")
    record(source, "B3", "ACCEPT")
    record(source, "B4", "ACCEPT")
    event = record(source, "B5", "REJECT")

    assert source.state == "TIGHTENED"
    assert event.to_state == "TIGHTENED"

def test_reduced_transition_uses_tenth_counted_lots_limits():
    source = SourceSwitchingState("SUP-TEST")

    ac = {"critical": 0, "major": 2, "minor": 5}
    re = {"critical": 1, "major": 5, "minor": 10}

    # First nine lots have a high major-defect reduced limit.
    for number in range(1, 10):
        source.record_inspection(
            batch_id=f"B{number}",
            decision="ACCEPT",
            defects={"critical": 0, "major": 0, "minor": 0},
            ac_limits=ac,
            re_limits=re,
            reduced_limits={"critical": 0, "major": 10, "minor": 10},
        )

    # The tenth lot has a major reduced limit of zero.
    source.record_inspection(
        batch_id="B10",
        decision="ACCEPT",
        defects={"critical": 0, "major": 1, "minor": 0},
        ac_limits=ac,
        re_limits=re,
        reduced_limits={"critical": 0, "major": 0, "minor": 10},
    )

    assert source.state == "NORMAL"
