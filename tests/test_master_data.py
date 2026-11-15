from pathlib import Path

from quality_engine.master_data import (
    load_products,
    load_sources,
    load_batches,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"

PRODUCTS = load_products(DATA_DIR / "products.csv")
SOURCES = load_sources(DATA_DIR / "sources.csv")
BATCHES = load_batches(
    DATA_DIR / "batches.csv",
    PRODUCTS,
    SOURCES,
)


def test_load_all_products():
    assert len(PRODUCTS) == 8


def test_load_all_sources():
    assert len(SOURCES) == 8


def test_load_all_batches():
    assert len(BATCHES) == 120


def test_product_has_shelf_life_and_aql_values():
    product = PRODUCTS["PRD-01"]

    assert product.shelf_life_days > 0
    assert product.aql_critical == "0.065"
    assert product.aql_major == "1.0"
    assert product.aql_minor in {"1.0", "2.5"}


def test_sources_have_valid_initial_states():
    for source in SOURCES.values():
        assert source.initial_state in {"NORMAL", "REDUCED"}


def test_batch_references_valid_product_and_source():
    for batch in BATCHES.values():
        assert batch.product_id in PRODUCTS
        assert batch.source_id in SOURCES


def test_batch_dates_are_valid():
    for batch in BATCHES.values():
        assert batch.expiry_date > batch.mfg_date


def test_batch_lot_size_is_positive():
    for batch in BATCHES.values():
        assert batch.lot_size > 0