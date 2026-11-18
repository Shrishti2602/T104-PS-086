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


def test_sampling_from_discontinued_source_is_refused_and_recorded(engine):
    batch_id = "BT-0001"
    batch = engine.batches[batch_id]

    engine.receive_batch(batch_id, "2026-05-04 09:48:00")

    # Put the batch's source into DISCONTINUED state.
    engine.source_states[batch.source_id].state = "DISCONTINUED"

    original_status = engine.batch_runtime[batch_id].status

    with pytest.raises(ValueError, match="DISCONTINUED"):
        engine.sample_batch(batch_id, "2026-05-04 12:04:00")

    # Sampling must remain blocked.
    assert engine.batch_runtime[batch_id].status == original_status

    # Exactly one refusal event must be recorded.
    refusal_events = [
        row for row in engine.release_register
        if row["batch_id"] == batch_id
        and row["event"] == "SAMPLE_REFUSED"
    ]

    assert len(refusal_events) == 1
    assert refusal_events[0]["from_status"] == original_status
    assert refusal_events[0]["to_status"] == original_status
    assert "DISCONTINUED" in refusal_events[0]["reason"]



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
    assert engine.batch_decisions[-1]["batch_status"] == "RECALLED"

    # Related eligible batches should also be recalled.
    recalled_ids = {
        batch_id
        for batch_id in related_ids
        if engine.batch_runtime[batch_id].status == "RECALLED"
    }

    assert target_id in recalled_ids
    assert len(recalled_ids) >= 1
    rule_ids = engine.batch_decisions[-1]["rule_ids"].split(";")

    assert "BR-11" in rule_ids
    assert "BR-12" in rule_ids

def test_result_exactly_48_hours_after_sampling_is_not_late(engine):
    engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    engine.sample_batch("BT-0001", "2026-05-04 12:04:00")

    engine.record_result(
        "BT-0001",
        "2026-05-06 12:04:00",
        0, 0, 0,
    )

    result = engine.batch_decisions[-1]
    assert result["late"] == "false"
    assert result["decision"] == "ACCEPT"


def test_result_48_hours_and_one_second_after_sampling_is_late(engine):
    engine.receive_batch("BT-0001", "2026-05-04 09:48:00")
    engine.sample_batch("BT-0001", "2026-05-04 12:04:00")

    engine.record_result(
        "BT-0001",
        "2026-05-06 12:04:01",
        0, 0, 0,
    )

    result = engine.batch_decisions[-1]
    assert result["late"] == "true"
    assert result["decision"] == "ACCEPT"

def test_release_allowed_with_exactly_75_percent_shelf_life_remaining(engine):
    from dataclasses import replace
    from datetime import date, timedelta

    batch_id = "BT-0001"
    batch = engine.batches[batch_id]
    product = engine.products[batch.product_id]

    mfg_date = date(2026, 1, 1)
    expiry_date = mfg_date + timedelta(days=100)

    engine.products[product.product_id] = replace(
        product, shelf_life_days=100
    )
    engine.batches[batch_id] = replace(
        batch, mfg_date=mfg_date, expiry_date=expiry_date
    )
    engine.source_states[batch.source_id].state = "NORMAL"

    engine.receive_batch(batch_id, "2026-01-25 09:00:00")
    engine.sample_batch(batch_id, "2026-01-25 10:00:00")
    engine.record_result(batch_id, "2026-01-26 10:00:00", 0, 0, 0)

    assert engine.batch_runtime[batch_id].status == "RELEASED"


def test_release_rejected_with_less_than_75_percent_shelf_life_remaining(engine):
    from dataclasses import replace
    from datetime import date, timedelta

    batch_id = "BT-0001"
    batch = engine.batches[batch_id]
    product = engine.products[batch.product_id]

    mfg_date = date(2026, 1, 1)
    expiry_date = mfg_date + timedelta(days=100)

    engine.products[product.product_id] = replace(
        product, shelf_life_days=100
    )
    engine.batches[batch_id] = replace(
        batch, mfg_date=mfg_date, expiry_date=expiry_date
    )
    engine.source_states[batch.source_id].state = "NORMAL"

    engine.receive_batch(batch_id, "2026-01-25 09:00:00")
    engine.sample_batch(batch_id, "2026-01-25 10:00:00")
    engine.record_result(batch_id, "2026-01-27 10:00:00", 0, 0, 0)

    assert engine.batch_runtime[batch_id].status == "REJECTED"
    assert engine.batch_decisions[-1]["decision"] == "ACCEPT"
    assert engine.release_register[-1]["reason"] == "SHORT_DATED"
def test_normal_inspection_records_base_rule_ids(engine):
    batch_id = "BT-0001"

    engine.receive_batch(batch_id, "2026-05-04 09:48:00")
    engine.sample_batch(batch_id, "2026-05-04 12:04:00")

    result = engine.record_result(
        batch_id, "2026-05-04 13:04:00", 0, 0, 0
    )

    rule_ids = result["rule_ids"].split(";")

    assert "BR-01" in rule_ids
    assert "BR-02" in rule_ids
    assert rule_ids == sorted(
        rule_ids, key=lambda rule: int(rule.split("-")[1])
    )


def test_late_result_records_br14(engine):
    batch_id = "BT-0001"

    engine.receive_batch(batch_id, "2026-05-04 09:48:00")
    engine.sample_batch(batch_id, "2026-05-04 12:04:00")

    result = engine.record_result(
        batch_id, "2026-05-06 12:04:01", 0, 0, 0
    )

    assert "BR-14" in result["rule_ids"].split(";")


def test_short_dated_result_records_br13(engine):
    from dataclasses import replace
    from datetime import date, timedelta

    batch_id = "BT-0001"
    batch = engine.batches[batch_id]
    product = engine.products[batch.product_id]

    mfg_date = date(2026, 1, 1)
    expiry_date = mfg_date + timedelta(days=100)

    engine.products[product.product_id] = replace(
        product, shelf_life_days=100
    )
    engine.batches[batch_id] = replace(
        batch, mfg_date=mfg_date, expiry_date=expiry_date
    )

    engine.receive_batch(batch_id, "2026-01-25 09:00:00")
    engine.sample_batch(batch_id, "2026-01-25 10:00:00")

    result = engine.record_result(
        batch_id, "2026-01-27 10:00:00", 0, 0, 0
    )

    assert result["decision"] == "ACCEPT"
    assert result["batch_status"] == "REJECTED"
    assert "BR-13" in result["rule_ids"].split(";")
