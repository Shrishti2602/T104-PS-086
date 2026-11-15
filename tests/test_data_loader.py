from pathlib import Path

import pytest

from quality_engine.data_loader import (
    code_for_lot_size,
    load_lot_size_bands,
    load_sampling_table,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"


def test_load_all_lot_size_bands():
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")

    assert len(bands) == 11


def test_lot_size_boundary_280_is_g():
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")

    assert code_for_lot_size(280, bands) == "G"


def test_lot_size_boundary_281_is_h():
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")

    assert code_for_lot_size(281, bands) == "H"


def test_invalid_lot_size_is_rejected():
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")

    with pytest.raises(ValueError):
        code_for_lot_size(1, bands)


def test_load_all_sampling_rules():
    rules = load_sampling_table(DATA_DIR / "sampling_table.csv")

    assert len(rules) == 99


def test_sampling_rule_lookup():
    rules = load_sampling_table(DATA_DIR / "sampling_table.csv")

    rule = rules[("A", "0.065", "NORMAL")]

    assert rule.sample_size == 200
    assert rule.ac == 0
    assert rule.re == 1
    assert rule.reduced_limit == 0