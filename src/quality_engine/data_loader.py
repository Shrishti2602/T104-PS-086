"""Load and validate the AQL engine's reference CSV files."""

import csv
from dataclasses import dataclass
from pathlib import Path


class DataValidationError(ValueError):
    """Raised when a reference CSV contains invalid data."""


@dataclass(frozen=True)
class LotSizeBand:
    lot_from: int
    lot_to: int
    code_letter: str


@dataclass(frozen=True)
class SamplingRule:
    code_letter: str
    aql: str
    severity: str
    sample_size: int
    ac: int
    re: int
    reduced_limit: int | None


LOT_COLUMNS = {"lot_from", "lot_to", "code_letter"}
SAMPLING_COLUMNS = {
    "code_letter", "aql", "severity", "sample_size",
    "ac", "re", "reduced_limit",
}
SEVERITIES = {"NORMAL", "TIGHTENED", "REDUCED"}


def _read_csv(path: Path, required_columns: set[str]) -> list[dict[str, str]]:
    """Read a CSV file and check that its required columns exist."""
    if not path.is_file():
        raise DataValidationError(f"CSV file not found: {path}")

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)

            if reader.fieldnames is None:
                raise DataValidationError(f"CSV file is empty: {path}")

            missing = required_columns - set(reader.fieldnames)
            if missing:
                raise DataValidationError(
                    f"{path.name}: missing columns {sorted(missing)}"
                )

            return list(reader)

    except UnicodeDecodeError as exc:
        raise DataValidationError(
            f"{path.name}: file must use UTF-8 encoding"
        ) from exc


def _to_int(value: str, field: str, filename: str, row_number: int) -> int:
    """Convert a CSV value to an integer with a useful error message."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise DataValidationError(
            f"{filename}, row {row_number}: "
            f"{field} must be an integer; received {value!r}"
        ) from exc


def load_lot_size_bands(path: str | Path) -> list[LotSizeBand]:
    """Load lot-size bands and validate their ranges."""
    file_path = Path(path)
    rows = _read_csv(file_path, LOT_COLUMNS)

    if not rows:
        raise DataValidationError("Lot-size bands file has no data rows.")

    bands = []
    for row_number, row in enumerate(rows, start=2):
        start = _to_int(row["lot_from"], "lot_from", file_path.name, row_number)
        end = _to_int(row["lot_to"], "lot_to", file_path.name, row_number)
        letter = row["code_letter"].strip()

        if start < 1 or end < start or not letter:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: invalid lot-size band"
            )

        bands.append(LotSizeBand(start, end, letter))

    bands.sort(key=lambda band: band.lot_from)

    for previous, current in zip(bands, bands[1:]):
        if current.lot_from <= previous.lot_to:
            raise DataValidationError("Lot-size bands overlap.")

        if current.lot_from != previous.lot_to + 1:
            raise DataValidationError("Lot-size bands contain a gap.")

    return bands


def code_for_lot_size(
    lot_size: int, bands: list[LotSizeBand]
) -> str:
    """Find the code letter for a given lot size."""
    if lot_size < 1:
        raise ValueError("Lot size must be positive.")

    for band in bands:
        if band.lot_from <= lot_size <= band.lot_to:
            return band.code_letter

    raise ValueError(f"No lot-size band found for lot size {lot_size}.")


def load_sampling_table(
    path: str | Path,
) -> dict[tuple[str, str, str], SamplingRule]:
    """Load sampling rules indexed by code letter, AQL and severity."""
    file_path = Path(path)
    rows = _read_csv(file_path, SAMPLING_COLUMNS)

    if not rows:
        raise DataValidationError("Sampling table has no data rows.")

    rules = {}

    for row_number, row in enumerate(rows, start=2):
        letter = row["code_letter"].strip()
        aql = row["aql"].strip()
        severity = row["severity"].strip().upper()

        if not letter or not aql:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: "
                "code_letter and aql cannot be empty."
            )

        if severity not in SEVERITIES:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: "
                f"invalid severity {severity!r}"
            )

        sample_size = _to_int(
            row["sample_size"], "sample_size", file_path.name, row_number
        )
        ac = _to_int(row["ac"], "ac", file_path.name, row_number)
        re = _to_int(row["re"], "re", file_path.name, row_number)

        reduced_value = row["reduced_limit"].strip()
        reduced_limit = (
            _to_int(
                reduced_value, "reduced_limit", file_path.name, row_number
            )
            if reduced_value else None
        )

        if sample_size < 1 or ac < 0 or re <= ac:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: "
                "invalid sample_size, Ac or Re values."
            )

        if severity == "NORMAL" and reduced_limit is None:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: "
                "NORMAL rules require reduced_limit."
            )

        if reduced_limit is not None and reduced_limit < 0:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: "
                "reduced_limit cannot be negative."
            )

        rule = SamplingRule(
            letter, aql, severity, sample_size, ac, re, reduced_limit
        )
        key = (letter, aql, severity)

        if key in rules:
            raise DataValidationError(
                f"{file_path.name}, row {row_number}: duplicate rule {key}"
            )

        rules[key] = rule

    return rules
