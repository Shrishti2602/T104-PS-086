
"""Manage inspection severity switching for each supplier or production line."""

from collections import deque
from dataclasses import dataclass, field


VALID_STATES = {"NORMAL", "TIGHTENED", "REDUCED", "DISCONTINUED"}
DEFECT_CLASSES = ("critical", "major", "minor")


@dataclass(frozen=True)
class SwitchingEvent:
    """Record a change in inspection severity."""

    source_id: str
    from_state: str
    to_state: str
    trigger_batch_id: str
    reason: str


@dataclass
class SourceSwitchingState:
    """Maintain independent switching history for one source."""

    source_id: str
    state: str = "NORMAL"
    normal_window: deque = field(
        default_factory=lambda: deque(maxlen=5)
    )
    tightened_accept_streak: int = 0
    tightened_rejection_count: int = 0
    reduced_window: deque = field(
        default_factory=lambda: deque(maxlen=10)
    )
    history: list[SwitchingEvent] = field(default_factory=list)

    def __post_init__(self):
        self.state = self.state.strip().upper()

        if self.state not in VALID_STATES:
            raise ValueError(f"Invalid initial state: {self.state}")

    def _transition(self, new_state, batch_id, reason):
        """Change the source state and record the transition."""
        old_state = self.state

        if old_state == new_state:
            return None

        self.state = new_state

        event = SwitchingEvent(
            source_id=self.source_id,
            from_state=old_state,
            to_state=new_state,
            trigger_batch_id=batch_id,
            reason=reason,
        )

        self.history.append(event)

        self.normal_window.clear()
        self.tightened_accept_streak = 0
        self.tightened_rejection_count = 0
        self.reduced_window.clear()

        return event

    def record_inspection(
        self,
        batch_id,
        decision,
        defects,
        ac_limits,
        re_limits,
        reduced_limits,
        late=False,
        first_inspection=True,
        production_irregularity=False,
    ):
        """Update switching state after an inspection result."""

        decision = decision.strip().upper()

        if decision not in {"ACCEPT", "REJECT"}:
            raise ValueError("Decision must be ACCEPT or REJECT.")

        for name, values in (
            ("defects", defects),
            ("ac_limits", ac_limits),
            ("re_limits", re_limits),
            ("reduced_limits", reduced_limits),
        ):
            if set(values) != set(DEFECT_CLASSES):
                raise ValueError(
                    f"{name} must contain critical, major and minor."
                )

        for defect_class in DEFECT_CLASSES:
            count = defects[defect_class]

            if (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                raise ValueError(
                    "Defect counts must be non-negative integers."
                )

        # No inspection is allowed while the source is discontinued.
        if self.state == "DISCONTINUED":
            raise ValueError(
                "Inspection is not allowed while the source is DISCONTINUED."
            )

        # Rework and hold reinspections do not affect switching.
        if not first_inspection:
            return None

        # A production gap or irregularity resets REDUCED to NORMAL.
        if self.state == "REDUCED" and production_irregularity:
            return self._transition(
                "NORMAL",
                batch_id,
                "Production irregularity.",
            )

        if self.state == "NORMAL":
            # Every first-inspection result counts in the five-batch
            # rejection window.
            self.normal_window.append(decision)

            if decision == "REJECT":
                self.reduced_window.clear()

                rejection_count = sum(
                    result == "REJECT"
                    for result in self.normal_window
                )

                if rejection_count >= 2:
                    return self._transition(
                        "TIGHTENED",
                        batch_id,
                        "2 rejections within 5 consecutive batches.",
                    )

            elif not late:
                # Late acceptances do not count toward the 10-lot
                # reduced-inspection qualification.
                self.reduced_window.append({
                    "defects": dict(defects),
                    "limits": dict(reduced_limits),
                })

                if len(self.reduced_window) == 10:
                    totals = {
                        defect_class: sum(
                            item["defects"][defect_class]
                            for item in self.reduced_window
                        )
                        for defect_class in DEFECT_CLASSES
                    }

                    tenth_limits = self.reduced_window[-1]["limits"]

                    within_limits = all(
                        totals[defect_class]
                        <= tenth_limits[defect_class]
                        for defect_class in DEFECT_CLASSES
                    )

                    if within_limits:
                        return self._transition(
                            "REDUCED",
                            batch_id,
                            "10 consecutive acceptances within reduced limits.",
                        )

        elif self.state == "TIGHTENED":
            if decision == "REJECT":
                self.tightened_rejection_count += 1
                self.tightened_accept_streak = 0

                # Rejections are cumulative, not necessarily consecutive.
                if self.tightened_rejection_count >= 5:
                    return self._transition(
                        "DISCONTINUED",
                        batch_id,
                        "5 rejections while in TIGHTENED state.",
                    )

            else:
                self.tightened_accept_streak += 1

                if self.tightened_accept_streak >= 5:
                    return self._transition(
                        "NORMAL",
                        batch_id,
                        "5 consecutive acceptances while TIGHTENED.",
                    )

        elif self.state == "REDUCED":
            if decision == "REJECT":
                return self._transition(
                    "NORMAL",
                    batch_id,
                    "Rejection while REDUCED.",
                )

            between_limits = any(
                defects[defect_class] > ac_limits[defect_class]
                and defects[defect_class] < re_limits[defect_class]
                for defect_class in DEFECT_CLASSES
            )

            if between_limits:
                return self._transition(
                    "NORMAL",
                    batch_id,
                    "Accepted result between Ac and Re while REDUCED.",
                )

        return None

    def corrective_action(self, batch_id, car_reference):
        """Resume inspection under TIGHTENED severity after corrective action."""

        if self.state != "DISCONTINUED":
            raise ValueError(
                "Corrective action is only accepted while DISCONTINUED."
            )

        if not isinstance(car_reference, str) or not car_reference.strip():
            raise ValueError(
                "Corrective action reference cannot be empty."
            )

        return self._transition(
            "TIGHTENED",
            batch_id,
            f"Corrective action recorded: {car_reference}.",
        )
