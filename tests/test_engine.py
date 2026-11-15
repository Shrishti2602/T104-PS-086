from pathlib import Path

import pytest

from quality_engine.data_loader import (
    load_lot_size_bands,
    load_sampling_table,
)
from quality_engine.master_data import (
    load_products,
    load_sources,
    load_batches,
)
from quality_engine.engine import BatchEngine


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


@pytest.fixture
def engine():
    products = load_products(DATA_DIR / "products.csv")
    sources = load_sources(DATA_DIR / "sources.csv")
    batches = load_batches(
        DATA_DIR / "batches.csv",
        products,
        sources,
    )
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")
    rules = load_sampling_table(DATA_DIR / "sampling_table.csv")

    return BatchEngine(products, sources, batches, bands, rules)


def test_receive_batch_places_batch_in_quarantine(engine):
    runtime = engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    assert runtime.status == "QUARANTINE"
    assert runtime.received_at is not None


def test_duplicate_batch_receipt_is_rejected(engine):
    engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    with pytest.raises(ValueError):
        engine.receive_batch("BT-0001", "2026-05-05 09:48:00")


def test_unknown_batch_receipt_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.receive_batch("BT-9999", "2026-05-04 09:48:00")


def test_sample_batch_changes_status(engine):
    engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    plan = engine.sample_batch("BT-0001", "2026-05-04 12:04:00")
    runtime = engine.batch_runtime["BT-0001"]
    assert runtime.status == "UNDER_INSPECTION"
    assert runtime.sampled_at is not None
    assert runtime.sample_plan is plan
    assert runtime.inspection_no == 1


def test_sampling_before_receipt_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.sample_batch("BT-0001", "2026-05-04 12:04:00")


def test_duplicate_sampling_without_hold_is_rejected(engine):
    engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    engine.sample_batch("BT-0001", "2026-05-04 12:04:00")
    with pytest.raises(ValueError):
        engine.sample_batch("BT-0001", "2026-05-04 13:04:00")


def test_invalid_timestamp_is_rejected(engine):
    with pytest.raises(ValueError):
        engine.receive_batch("BT-0001", "04-05-2026")


def _prepare_hold_scenario(engine):
    target_id, cause_id = "BT-0001", "BT-0011"
    engine.receive_batch(target_id, "2026-05-04 09:00:00")
    engine.receive_batch(cause_id, "2026-05-04 09:01:00")
    target = engine.batch_runtime[target_id]
    cause = engine.batch_runtime[cause_id]
    target.status = "RELEASED"
    target.release_at = engine._parse_timestamp("2026-05-04 10:00:00")
    cause.status = "REJECTED"
    engine.batch_decisions.append({
        "batch_id": cause_id,
        "decision": "REJECT",
        "critical": 1,
        "major": 0,
        "minor": 0,
    })
    return target_id, cause_id


def test_hold_request_is_accepted_on_day_30(engine):
    target_id, cause_id = _prepare_hold_scenario(engine)
    accepted = engine.hold_request(
        target_id, "2026-06-03 10:00:00", cause_id
    )
    assert accepted is True
    assert engine.batch_runtime[target_id].status == "ON_HOLD"


def test_hold_request_is_refused_on_day_31(engine):
    target_id, cause_id = _prepare_hold_scenario(engine)
    accepted = engine.hold_request(
        target_id, "2026-06-04 10:00:00", cause_id
    )
    assert accepted is False
    assert engine.batch_runtime[target_id].status == "RELEASED"


def prepare_recall_scenario(engine):
    """Prepare all batches sharing BT-0073's raw-material lot."""
    complaint_batch = engine.batches["BT-0073"]
    related_ids = [
        batch_id
        for batch_id, batch in engine.batches.items()
        if batch.rm_lot == complaint_batch.rm_lot
    ]
    for batch_id in related_ids:
        engine.receive_batch(batch_id, "2026-08-01 09:00:00")
        engine.batch_runtime[batch_id].status = "RELEASED"
    return related_ids


def test_complaint_recalls_related_batches(engine):
    prepare_recall_scenario(engine)
    recalled = engine.complaint(
        "BT-0073", "2026-09-11 18:00:00", "CMP-TEST-01"
    )
    assert "BT-0073" in recalled
    assert "BT-0072" in recalled
    assert "BT-0035" in recalled
    assert "BT-0045" in recalled
    assert engine.batch_runtime["BT-0073"].status == "RECALLED"
    assert engine.batch_runtime["BT-0072"].status == "RECALLED"


def test_complaint_does_not_recall_expired_batch(engine):
    prepare_recall_scenario(engine)
    engine.complaint("BT-0073", "2026-09-11 18:00:00", "CMP-TEST-02")
    assert engine.batch_runtime["BT-0016"].status == "RELEASED"
    event = next(
        row for row in engine.release_register
        if row["batch_id"] == "BT-0016"
    )
    assert event["event"] == "NOT_RECALLED_EXPIRED"
    assert event["to_status"] == "RELEASED"


def test_corrective_action_resumes_discontinued_source_at_tightened(engine):
    source_id = next(iter(engine.source_states))

    # Set up the source in DISCONTINUED state for this test.
    engine.source_states[source_id].state = "DISCONTINUED"

    event = engine.corrective_action(
        source_id,
        "2026-10-01 09:00:00",
        "CAR-TEST-01",
    )

    assert engine.source_states[source_id].state == "TIGHTENED"
    assert event.from_state == "DISCONTINUED"
    assert event.to_state == "TIGHTENED"

    history = engine.switching_history[-1]
    assert history["timestamp"] == "2026-10-01 09:00:00"
    assert history["to_state"] == "TIGHTENED"


def test_corrective_action_is_refused_when_source_not_discontinued(engine):
    source_id = next(
        source_id for source_id, state in engine.source_states.items()
        if state.state != "DISCONTINUED"
    )
    with pytest.raises(ValueError):
        engine.corrective_action(
            source_id, "2026-10-01 09:00:00", "CAR-TEST-02"
        )
def test_critical_defect_during_hold_reinspection_triggers_recall(engine):
    related_ids = prepare_recall_scenario(engine)

    target_id = "BT-0073"
    runtime = engine.batch_runtime[target_id]

    # Place the target batch on hold.
    runtime.status = "ON_HOLD"

    # Ensure sampling is allowed.
    batch = engine.batches[target_id]
    engine.source_states[batch.source_id].state = "NORMAL"

    # Perform hold reinspection.
    engine.sample_batch(
        target_id,
        "2026-08-02 09:00:00",
    )

    assert runtime.hold_reinspection is True

    # Record a critical defect.
    engine.record_result(
        target_id,
        "2026-08-02 12:00:00",
        critical=1,
        major=0,
        minor=0,
    )

    # The critical defect must automatically trigger recall.
    assert runtime.status == "RECALLED"

    # Related eligible batches should also be recalled.
    recalled_ids = {
        batch_id
        for batch_id in related_ids
        if engine.batch_runtime[batch_id].status == "RECALLED"
    }

    assert target_id in recalled_ids
    assert len(recalled_ids) >= 1