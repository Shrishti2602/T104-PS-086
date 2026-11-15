
"""Create inspection sample plans from the supplied AQL sampling table."""

from dataclasses import dataclass
from decimal import Decimal

from quality_engine.data_loader import (
    LotSizeBand,
    SamplingRule,
    code_for_lot_size,
)


@dataclass(frozen=True)
class SamplingPlan:
    """Sampling requirements for one batch."""

    code_letter: str
    severity: str
    n_critical: int
    n_major: int
    n_minor: int
    full_inspection: bool
    critical_rule: SamplingRule
    major_rule: SamplingRule
    minor_rule: SamplingRule


def _normalise_aql(value: str | int | float | Decimal) -> str:
    """Make AQL values match the format used in the CSV file."""
    return format(Decimal(str(value)), "f")


def plan_sampling(
    lot_size: int,
    aql_critical: str | int | float,
    aql_major: str | int | float,
    aql_minor: str | int | float,
    severity: str,
    bands: list[LotSizeBand],
    rules: dict[tuple[str, str, str], SamplingRule],
) -> SamplingPlan:
    """Calculate the sample plan for critical, major and minor defects."""
    if lot_size < 1:
        raise ValueError("Lot size must be positive.")

    severity = severity.strip().upper()
    if severity not in {"NORMAL", "TIGHTENED", "REDUCED"}:
        raise ValueError(f"Invalid inspection severity: {severity!r}")

    code_letter = code_for_lot_size(lot_size, bands)

    def get_rule(aql: str | int | float) -> SamplingRule:
        key = (code_letter, _normalise_aql(aql), severity)
        try:
            return rules[key]
        except KeyError as exc:
            raise ValueError(f"No sampling rule found for {key}.") from exc

    critical_rule = get_rule(aql_critical)
    major_rule = get_rule(aql_major)
    minor_rule = get_rule(aql_minor)

    largest_sample = max(
        critical_rule.sample_size,
        major_rule.sample_size,
        minor_rule.sample_size,
    )
    full_inspection = largest_sample >= lot_size

    if full_inspection:
        n_critical = n_major = n_minor = lot_size
    else:
        n_critical = critical_rule.sample_size
        n_major = major_rule.sample_size
        n_minor = minor_rule.sample_size

    return SamplingPlan(
        code_letter=code_letter,
        severity=severity,
        n_critical=n_critical,
        n_major=n_major,
        n_minor=n_minor,
        full_inspection=full_inspection,
        critical_rule=critical_rule,
        major_rule=major_rule,
        minor_rule=minor_rule,
    )
