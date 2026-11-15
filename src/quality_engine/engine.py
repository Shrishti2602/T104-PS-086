

"""Central engine for batch inspection and release processing."""

from dataclasses import dataclass, replace

from datetime import datetime, timedelta

from quality_engine.sampling import plan_sampling

from quality_engine.inspection import evaluate_inspection

from quality_engine.switching import SourceSwitchingState

@dataclass

class BatchRuntime:

    """Store the changing status and inspection details of a batch."""

    batch_id: str

    status: str = "NOT_RECEIVED"

    received_at: datetime | None = None

    sampled_at: datetime | None = None

    sample_plan: object | None = None

    sampled_state: str | None = None

    inspection_no: int = 0

    reworked: bool = False

    hold_reinspection: bool = False

    release_at: datetime | None = None

    production_irregularity: bool = False

class BatchEngine:

    """Coordinate batch processing using quality-control rules."""

    def __init__(

        self,

        products,

        sources,

        batches,

        lot_size_bands,

        sampling_rules,

    ):

        self.products = products

        self.sources = sources

        self.batches = batches

        self.lot_size_bands = lot_size_bands

        self.sampling_rules = sampling_rules

        self.source_states = {

            source_id: SourceSwitchingState(

                source_id=source_id,

                state=source.initial_state,

            )

            for source_id, source in sources.items()

        }

        self.last_receive_date = {

            source_id: source.last_batch_date

            for source_id, source in sources.items()

        }

        self.batch_runtime = {}

        self.batch_decisions = []

        self.release_register = []
        self.switching_history = []
        self._switching_events_captured = {
            source_id: 0 for source_id in self.source_states
        }

    @staticmethod

    def _parse_timestamp(value):

        """Convert a timestamp string into a datetime object."""

        if isinstance(value, datetime):

            return value

        try:

            return datetime.strptime(

                value, "%Y-%m-%d %H:%M:%S"

            )

        except (TypeError, ValueError) as exc:

            raise ValueError(

                "Timestamp must use YYYY-MM-DD HH:MM:SS format."

            ) from exc

    def _capture_switching_events(self, source_id, timestamp):
        """Copy newly recorded source transitions into engine history."""

        source_state = self.source_states[source_id]
        captured = self._switching_events_captured[source_id]

        for event in source_state.history[captured:]:
            self.switching_history.append({
                "source_id": event.source_id,
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "from_state": event.from_state,
                "to_state": event.to_state,
                "trigger_batch_id": event.trigger_batch_id,
                "reason": event.reason,
            })

        self._switching_events_captured[source_id] = len(
            source_state.history
        )

    def receive_batch(self, batch_id, timestamp):

        """Receive a batch and place it in QUARANTINE."""

        if batch_id not in self.batches:

            raise ValueError(f"Unknown batch ID: {batch_id}")

        if batch_id in self.batch_runtime:

            raise ValueError(

                f"Batch {batch_id} has already been received."

            )

        received_at = self._parse_timestamp(timestamp)

        batch = self.batches[batch_id]

        source = self.sources[batch.source_id]

        previous_date = self.last_receive_date[batch.source_id]

        production_irregularity = False

        if (

            source.source_type == "LINE"

            and previous_date is not None

        ):

            gap_days = (received_at.date() - previous_date).days

            production_irregularity = gap_days > 30

        runtime = BatchRuntime(

            batch_id=batch_id,

            status="QUARANTINE",

            received_at=received_at,

            production_irregularity=production_irregularity,

        )

        self.batch_runtime[batch_id] = runtime

        self.last_receive_date[batch.source_id] = received_at.date()

        return runtime

    def sample_batch(self, batch_id, timestamp):

        """Plan and record a batch sample."""

        if batch_id not in self.batch_runtime:

            raise ValueError(

                f"Batch {batch_id} has not been received."

            )

        runtime = self.batch_runtime[batch_id]

        if runtime.status not in {"QUARANTINE", "ON_HOLD"}:

            raise ValueError(

                f"Cannot sample batch {batch_id} "

                f"while its status is {runtime.status}."

            )

        sampled_at = self._parse_timestamp(timestamp)

        batch = self.batches[batch_id]

        product = self.products[batch.product_id]

        source_state = self.source_states[batch.source_id]

        if source_state.state == "DISCONTINUED":

            raise ValueError(

                f"Sampling refused: source {batch.source_id} "

                "is DISCONTINUED."

            )

        if (

            runtime.production_irregularity

            and source_state.state == "REDUCED"

        ):

            source_state._transition(

                "NORMAL",

                batch_id,

                "Production gap greater than 30 days.",

            )
            self._capture_switching_events(batch.source_id, sampled_at)

        severity = source_state.state

        if runtime.reworked:

            severity = "TIGHTENED"

        was_on_hold = runtime.status == "ON_HOLD"

        plan = plan_sampling(

            lot_size=batch.lot_size,

            aql_critical=product.aql_critical,

            aql_major=product.aql_major,

            aql_minor=product.aql_minor,

            severity=severity,

            bands=self.lot_size_bands,

            rules=self.sampling_rules,

        )

        if was_on_hold:

            doubled_critical = plan.n_critical * 2

            doubled_major = plan.n_major * 2

            doubled_minor = plan.n_minor * 2

            largest_sample = max(

                doubled_critical,

                doubled_major,

                doubled_minor,

            )

            if largest_sample >= batch.lot_size:

                plan = replace(

                    plan,

                    n_critical=batch.lot_size,

                    n_major=batch.lot_size,

                    n_minor=batch.lot_size,

                    full_inspection=True,

                )

            else:

                plan = replace(

                    plan,

                    n_critical=doubled_critical,

                    n_major=doubled_major,

                    n_minor=doubled_minor,

                )

        runtime.sampled_at = sampled_at

        runtime.sample_plan = plan

        runtime.sampled_state = severity

        runtime.hold_reinspection = was_on_hold

        runtime.status = "UNDER_INSPECTION"

        runtime.inspection_no += 1

        return plan

    def record_result(

        self,

        batch_id,

        timestamp,

        critical,

        major,

        minor,

    ):

        """Evaluate inspection results and update batch status."""

        if batch_id not in self.batch_runtime:

            raise ValueError(

                f"Batch {batch_id} has not been received."

            )

        runtime = self.batch_runtime[batch_id]

        if runtime.status != "UNDER_INSPECTION":

            raise ValueError(

                f"Cannot record results for {batch_id} "

                f"while its status is {runtime.status}."

            )

        if runtime.sample_plan is None or runtime.sampled_at is None:

            raise ValueError("Batch has no valid sampling plan.")

        result_time = self._parse_timestamp(timestamp)

        if result_time < runtime.sampled_at:

            raise ValueError(

                "Result timestamp cannot be earlier than sampling."

            )

        plan = runtime.sample_plan

        batch = self.batches[batch_id]

        product = self.products[batch.product_id]

        late = (

            result_time - runtime.sampled_at

        ) > timedelta(hours=48)

        inspection = evaluate_inspection(

            critical=critical,

            major=major,

            minor=minor,

            critical_rule=plan.critical_rule,

            major_rule=plan.major_rule,

            minor_rule=plan.minor_rule,

        )

        decision = inspection.decision

        reason = inspection.reason

        batch_status = (

            "RELEASED" if decision == "ACCEPT" else "REJECTED"

        )

        if decision == "ACCEPT":

            remaining_days = (

                batch.expiry_date - result_time.date()

            ).days

            if remaining_days < 0.75 * product.shelf_life_days:

                batch_status = "REJECTED"

                reason = "SHORT_DATED"

        previous_status = runtime.status

        runtime.status = batch_status

        if batch_status == "RELEASED":

            runtime.release_at = result_time

        first_inspection = (

            runtime.inspection_no == 1

            and not runtime.reworked

            and not runtime.hold_reinspection

        )

        source_state = self.source_states[batch.source_id]

        normal_rules = {

            "critical": self.sampling_rules[

                (plan.code_letter, product.aql_critical, "NORMAL")

            ],

            "major": self.sampling_rules[

                (plan.code_letter, product.aql_major, "NORMAL")

            ],

            "minor": self.sampling_rules[

                (plan.code_letter, product.aql_minor, "NORMAL")

            ],

        }

        defects = {

            "critical": critical,

            "major": major,

            "minor": minor,

        }

        ac_limits = {

            "critical": plan.critical_rule.ac,

            "major": plan.major_rule.ac,

            "minor": plan.minor_rule.ac,

        }

        re_limits = {

            "critical": plan.critical_rule.re,

            "major": plan.major_rule.re,

            "minor": plan.minor_rule.re,

        }

        reduced_limits = {

            name: rule.reduced_limit

            for name, rule in normal_rules.items()

        }

        # A SHORT_DATED rejection counts as an acceptance
        # for severity switching because inspection passed.
        source_state.record_inspection(

            batch_id=batch_id,

            decision=decision,

            defects=defects,

            ac_limits=ac_limits,

            re_limits=re_limits,

            reduced_limits=reduced_limits,

            late=late,

            first_inspection=first_inspection,

        )
        self._capture_switching_events(batch.source_id, result_time)

        decision_row = {

            "batch_id": batch_id,

            "inspection_no": runtime.inspection_no,

            "source_state": runtime.sampled_state,

            "code_letter": plan.code_letter,

            "n_critical": plan.n_critical,

            "n_major": plan.n_major,

            "n_minor": plan.n_minor,

            "full_inspection": str(plan.full_inspection).lower(),

            "critical": critical,

            "major": major,

            "minor": minor,

            "ac_major": plan.major_rule.ac,

            "re_major": plan.major_rule.re,

            "ac_minor": plan.minor_rule.ac,

            "re_minor": plan.minor_rule.re,

            "decision": decision,

            "batch_status": batch_status,

            "late": str(late).lower(),

            "rule_ids": "",

        }

        self.batch_decisions.append(decision_row)

        self.release_register.append({

            "timestamp": result_time.strftime(

                "%Y-%m-%d %H:%M:%S"

            ),

            "batch_id": batch_id,

            "event": batch_status,

            "from_status": previous_status,

            "to_status": batch_status,

            "reason": reason,

            "cause_ref": "",

        })

        return decision_row

    def rework_batch(self, batch_id, timestamp):

        """Allow eligible rejected batches to undergo rework."""

        if batch_id not in self.batch_runtime:

            raise ValueError(

                f"Batch {batch_id} has not been received."

            )

        runtime = self.batch_runtime[batch_id]

        if runtime.status != "REJECTED":

            raise ValueError(

                "Only REJECTED batches can be reworked."

            )

        if runtime.reworked:

            raise ValueError(

                "A batch can only be reworked once."

            )

        if runtime.sample_plan is None:

            raise ValueError("Batch has no inspection plan.")

        # Use the most recent inspection's results.
        if not self.batch_decisions:

            raise ValueError("No inspection result is available.")

        last_result = next(

            (

                row for row in reversed(self.batch_decisions)

                if row["batch_id"] == batch_id

            ),

            None,

        )

        if last_result is None:

            raise ValueError("No inspection result is available.")

        if last_result["critical"] != 0:

            raise ValueError(

                "Rework refused: critical defects must be zero."

            )

        major_re_limit = runtime.sample_plan.major_rule.re

        if last_result["major"] > 2 * major_re_limit:

            raise ValueError(

                "Rework refused: major defects exceed twice Re."

            )

        rework_time = self._parse_timestamp(timestamp)

        if (

            runtime.sampled_at is not None

            and rework_time < runtime.sampled_at

        ):

            raise ValueError(

                "Rework timestamp cannot be earlier than sampling."

            )

        previous_status = runtime.status

        runtime.status = "QUARANTINE"

        runtime.reworked = True

        runtime.hold_reinspection = False

        runtime.sampled_at = None

        runtime.sample_plan = None

        runtime.sampled_state = None

        self.release_register.append({

            "timestamp": rework_time.strftime(

                "%Y-%m-%d %H:%M:%S"

            ),

            "batch_id": batch_id,

            "event": "REWORK",

            "from_status": previous_status,

            "to_status": "QUARANTINE",

            "reason": "Rework accepted; next inspection uses TIGHTENED severity.",

            "cause_ref": "",

        })

        return runtime

    def hold_request(self, batch_id, timestamp, cause_batch_id):

        """Place a released related batch ON_HOLD after a critical rejection."""

        if batch_id not in self.batches:

            raise ValueError(f"Unknown batch ID: {batch_id}")

        request_time = self._parse_timestamp(timestamp)

        runtime = self.batch_runtime.get(batch_id)

        reason = ""

        accepted = True

        if runtime is None or runtime.status != "RELEASED":

            accepted = False

            reason = "Target batch is not RELEASED."

        elif cause_batch_id not in self.batches:

            accepted = False

            reason = "Cause batch does not exist."

        else:

            target = self.batches[batch_id]

            cause = self.batches[cause_batch_id]

            cause_runtime = self.batch_runtime.get(cause_batch_id)

            if (

                target.source_id != cause.source_id

                or target.rm_lot != cause.rm_lot

            ):

                accepted = False

                reason = "Batches do not share the same source and RM lot."

            elif cause_runtime is None or cause_runtime.status != "REJECTED":

                accepted = False

                reason = "Cause batch is not REJECTED."

            else:

                cause_result = next(

                    (

                        row for row in reversed(self.batch_decisions)

                        if row["batch_id"] == cause_batch_id

                    ),

                    None,

                )

                if (

                    cause_result is None

                    or cause_result["decision"] != "REJECT"

                    or cause_result["critical"] <= 0

                ):

                    accepted = False

                    reason = "Cause batch was not rejected for a critical defect."

                elif runtime.release_at is None:

                    accepted = False

                    reason = "Target batch has no release timestamp."

                else:

                    days_after_release = (

                        request_time.date() - runtime.release_at.date()

                    ).days

                    if days_after_release < 0:

                        accepted = False

                        reason = "Hold request is before the release date."

                    elif days_after_release > 30:

                        accepted = False

                        reason = "Hold request is more than 30 days after release."

        previous_status = (

            runtime.status if runtime is not None else "UNKNOWN"

        )

        if accepted:

            runtime.status = "ON_HOLD"

            event = "ON_HOLD"

            new_status = "ON_HOLD"

            reason = "Related batch rejected for a critical defect."

        else:

            event = "HOLD_REFUSED"

            new_status = previous_status

        self.release_register.append({

            "timestamp": request_time.strftime("%Y-%m-%d %H:%M:%S"),

            "batch_id": batch_id,

            "event": event,

            "from_status": previous_status,

            "to_status": new_status,

            "reason": reason,

            "cause_ref": cause_batch_id,

        })

        return accepted

    def complaint(self, batch_id, timestamp, complaint_ref):

        """Recall a batch and eligible related batches sharing its RM lot."""

        if batch_id not in self.batches:

            raise ValueError(f"Unknown batch ID: {batch_id}")

        recall_time = self._parse_timestamp(timestamp)

        complaint_batch = self.batches[batch_id]

        complaint_runtime = self.batch_runtime.get(batch_id)

        if complaint_runtime is None:

            raise ValueError("Complaint batch has not been received.")

        if complaint_runtime.status not in {"RELEASED", "ON_HOLD"}:

            raise ValueError(

                "Complaint batch must be RELEASED or ON_HOLD."

            )

        recalled_batches = []

        for related_id, related_batch in self.batches.items():

            if related_batch.rm_lot != complaint_batch.rm_lot:

                continue

            runtime = self.batch_runtime.get(related_id)

            if runtime is None:

                continue

            if runtime.status not in {"RELEASED", "ON_HOLD"}:

                continue

            previous_status = runtime.status

            if related_batch.expiry_date < recall_time.date():

                event = "NOT_RECALLED_EXPIRED"

                new_status = previous_status

                reason = "Batch expired before the recall date."

            else:

                event = "RECALLED"

                new_status = "RECALLED"

                reason = "Customer complaint recall cascade."

                runtime.status = "RECALLED"

                recalled_batches.append(related_id)

            self.release_register.append({

                "timestamp": recall_time.strftime(

                    "%Y-%m-%d %H:%M:%S"

                ),

                "batch_id": related_id,

                "event": event,

                "from_status": previous_status,

                "to_status": new_status,

                "reason": reason,

                "cause_ref": complaint_ref,

            })

        return recalled_batches

    def corrective_action(self, source_id, timestamp, car_reference):
        """Resume a discontinued source at TIGHTENED severity."""

        if source_id not in self.source_states:
            raise ValueError(f"Unknown source ID: {source_id}")

        action_time = self._parse_timestamp(timestamp)
        source_state = self.source_states[source_id]
        event = source_state.corrective_action(
            batch_id="",
            car_reference=car_reference,
        )

        self._capture_switching_events(source_id, action_time)

        return event
