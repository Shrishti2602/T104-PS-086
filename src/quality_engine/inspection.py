
"""Evaluate inspection results against AQL acceptance limits."""

from dataclasses import dataclass

from quality_engine.data_loader import SamplingRule


@dataclass(frozen=True)
class InspectionResult:
    """Final decision and defect counts for an inspection."""

    critical: int
    major: int
    minor: int
    decision: str
    reason: str


def evaluate_inspection(
    critical: int,
    major: int,
    minor: int,
    critical_rule: SamplingRule,
    major_rule: SamplingRule,
    minor_rule: SamplingRule,
) -> InspectionResult:
    """Accept or reject a batch using each defect class's own limits."""

    counts = {
        "critical": critical,
        "major": major,
        "minor": minor,
    }

    for defect_class, count in counts.items():
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(
                f"{defect_class} defect count must be a non-negative integer."
            )

    failures = []

    if critical >= 1:
        failures.append(
            f"critical defects {critical} reached Re={critical_rule.re}"
        )

    if major >= major_rule.re:
        failures.append(
            f"major defects {major} reached Re={major_rule.re}"
        )

    if minor >= minor_rule.re:
        failures.append(
            f"minor defects {minor} reached Re={minor_rule.re}"
        )

    if failures:
        return InspectionResult(
            critical, major, minor, "REJECT", "; ".join(failures)
        )

    return InspectionResult(
        critical, major, minor, "ACCEPT",
        "All defect counts are below their rejection limits."
    )
