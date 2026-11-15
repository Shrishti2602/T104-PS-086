
"""Load product, source and batch master data."""

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class MasterDataError(ValueError):
    """Raised when master data is missing or invalid."""


@dataclass(frozen=True)
class Product:
    product_id: str
    product_name: str
    category: str
    shelf_life_days: int
    aql_critical: str
    aql_major: str
    aql_minor: str


@dataclass(frozen=True)
class Source:
    source_id: str
    source_type: str
    source_name: str
    location: str
    initial_state: str
    last_batch_date: date | None


@dataclass(frozen=True)
class Batch:
    batch_id: str
    product_id: str
    source_id: str
    rm_lot: str
    lot_size: int
    mfg_date: date
    expiry_date: date


def _read_rows(path, required_columns):
    """Read a CSV and verify its required columns."""
    path = Path(path)

    if not path.is_file():
        raise MasterDataError(f"File not found: {path}")

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise MasterDataError(f"Empty CSV file: {path.name}")

            missing = required_columns - set(reader.fieldnames)
            if missing:
                raise MasterDataError(
                    f"{path.name}: missing columns {sorted(missing)}"
                )

            return list(reader)

    except UnicodeDecodeError as exc:
        raise MasterDataError(
            f"{path.name} must use UTF-8 encoding."
        ) from exc


def _required_text(row, field, filename, row_number):
    value = row[field].strip()

    if not value:
        raise MasterDataError(
            f"{filename}, row {row_number}: {field} cannot be empty."
        )

    return value


def _positive_integer(value, field, filename, row_number):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise MasterDataError(
            f"{filename}, row {row_number}: {field} must be an integer."
        ) from exc

    if number <= 0:
        raise MasterDataError(
            f"{filename}, row {row_number}: {field} must be positive."
        )

    return number


def _parse_date(value, field, filename, row_number, optional=False):
    value = value.strip()

    if not value and optional:
        return None

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise MasterDataError(
            f"{filename}, row {row_number}: "
            f"{field} must use YYYY-MM-DD format."
        ) from exc


def load_products(path):
    """Load and validate product records."""
    required = {
        "product_id", "product_name", "category",
        "shelf_life_days", "aql_critical",
        "aql_major", "aql_minor",
    }

    rows = _read_rows(path, required)
    products = {}

    for number, row in enumerate(rows, start=2):
        filename = Path(path).name

        product = Product(
            product_id=_required_text(
                row, "product_id", filename, number
            ),
            product_name=_required_text(
                row, "product_name", filename, number
            ),
            category=_required_text(
                row, "category", filename, number
            ).upper(),
            shelf_life_days=_positive_integer(
                row["shelf_life_days"], "shelf_life_days",
                filename, number
            ),
            aql_critical=_required_text(
                row, "aql_critical", filename, number
            ),
            aql_major=_required_text(
                row, "aql_major", filename, number
            ),
            aql_minor=_required_text(
                row, "aql_minor", filename, number
            ),
        )

        if product.category not in {"PHARMA", "FOOD"}:
            raise MasterDataError(
                f"{filename}, row {number}: invalid category."
            )

        if product.product_id in products:
            raise MasterDataError(
                f"{filename}, row {number}: duplicate product ID."
            )

        products[product.product_id] = product

    if not products:
        raise MasterDataError("Products file has no data rows.")

    return products


def load_sources(path):
    """Load and validate supplier and production-line records."""
    required = {
        "source_id", "source_type", "source_name",
        "location", "initial_state", "last_batch_date",
    }

    rows = _read_rows(path, required)
    sources = {}

    for number, row in enumerate(rows, start=2):
        filename = Path(path).name

        source_type = _required_text(
            row, "source_type", filename, number
        ).upper()

        initial_state = _required_text(
            row, "initial_state", filename, number
        ).upper()

        if source_type not in {"SUPPLIER", "LINE"}:
            raise MasterDataError(
                f"{filename}, row {number}: invalid source_type."
            )

        if initial_state not in {"NORMAL", "REDUCED"}:
            raise MasterDataError(
                f"{filename}, row {number}: invalid initial_state."
            )

        source = Source(
            source_id=_required_text(
                row, "source_id", filename, number
            ),
            source_type=source_type,
            source_name=_required_text(
                row, "source_name", filename, number
            ),
            location=_required_text(
                row, "location", filename, number
            ),
            initial_state=initial_state,
            last_batch_date=_parse_date(
                row["last_batch_date"], "last_batch_date",
                filename, number, optional=True
            ),
        )

        if source.source_id in sources:
            raise MasterDataError(
                f"{filename}, row {number}: duplicate source ID."
            )

        sources[source.source_id] = source

    if not sources:
        raise MasterDataError("Sources file has no data rows.")

    return sources


def load_batches(path, products, sources):
    """Load batches and validate their product and source references."""
    required = {
        "batch_id", "product_id", "source_id",
        "rm_lot", "lot_size", "mfg_date", "expiry_date",
    }

    rows = _read_rows(path, required)
    batches = {}

    for number, row in enumerate(rows, start=2):
        filename = Path(path).name

        batch = Batch(
            batch_id=_required_text(
                row, "batch_id", filename, number
            ),
            product_id=_required_text(
                row, "product_id", filename, number
            ),
            source_id=_required_text(
                row, "source_id", filename, number
            ),
            rm_lot=_required_text(
                row, "rm_lot", filename, number
            ),
            lot_size=_positive_integer(
                row["lot_size"], "lot_size", filename, number
            ),
            mfg_date=_parse_date(
                row["mfg_date"], "mfg_date", filename, number
            ),
            expiry_date=_parse_date(
                row["expiry_date"], "expiry_date", filename, number
            ),
        )

        if batch.product_id not in products:
            raise MasterDataError(
                f"{filename}, row {number}: "
                f"unknown product {batch.product_id}."
            )

        if batch.source_id not in sources:
            raise MasterDataError(
                f"{filename}, row {number}: "
                f"unknown source {batch.source_id}."
            )

        if batch.expiry_date <= batch.mfg_date:
            raise MasterDataError(
                f"{filename}, row {number}: "
                "expiry_date must be after mfg_date."
            )

        if batch.batch_id in batches:
            raise MasterDataError(
                f"{filename}, row {number}: duplicate batch ID."
            )

        batches[batch.batch_id] = batch

    if not batches:
        raise MasterDataError("Batches file has no data rows.")

    return batches
