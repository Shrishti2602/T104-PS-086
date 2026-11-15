# PS-086 – AQL Sampling, Inspection Severity and Batch Release Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T104.

## Files

| File | What it holds | Row count |
|---|---|---|
| `products.csv` | 8 products with shelf life and AQL per defect class | 8 data rows |
| `sources.csv` | 6 suppliers and 2 production lines with their switching state on 2026-05-01 | 8 data rows |
| `lot_size_bands.csv` | Lot-size bands -> code letter | 11 data rows |
| `sampling_table.csv` | Sample size n, Ac, Re per code letter, AQL and severity; reduced_limit for the NORMAL -> REDUCED test | 99 data rows |
| `batches.csv` | Batches (incoming and production) with lot size, raw-material lot, mfg and expiry dates | 120 data rows |
| `commands.txt` | Receipts, sampling, inspection results, rework, hold requests, complaints, corrective actions and prints | 382 command lines (excluding comments) |

Row numbers quoted below are 1-based data-row numbers (the header is row 0). Line numbers for `commands.txt` are physical line numbers including comment lines.

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with 2 places (no commas, no symbol); percentages as plain numbers (12.5 means 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix. An empty cell means "not applicable" and only occurs in columns whose notes say so.

### `products.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| product_id | string | PRD-nn | — | — |
| product_name | string | — | — | — |
| category | enum | — | PHARMA, FOOD | — |
| shelf_life_days | int | days | — | = expiry_date - mfg_date |
| aql_critical | string | AQL % | 0.065 | matches sampling_table.aql |
| aql_major | string | AQL % | 1.0 | — |
| aql_minor | string | AQL % | 1.0, 2.5 | — |

### `sources.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| source_id | string | SUP-nn / LINE-nn | — | — |
| source_type | enum | — | SUPPLIER, LINE | — |
| source_name | string | — | — | — |
| location | string | — | — | — |
| initial_state | enum | — | NORMAL, REDUCED | state at the start of the file |
| last_batch_date | date | — | — | date of the last batch before this file (for the 30-day gap rule) |

### `lot_size_bands.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| lot_from | int | units | — | inclusive |
| lot_to | int | units | — | inclusive |
| code_letter | string | — | A..L (no I) | — |

### `sampling_table.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| code_letter | string | — | A..L | — |
| aql | string | — | 0.065, 1.0, 2.5 | — |
| severity | enum | — | NORMAL, TIGHTENED, REDUCED | — |
| sample_size | int | units | — | if >= lot size inspect 100% (n = lot size); Ac/Re unchanged |
| ac | int | — | — | accept if defects <= Ac |
| re | int | — | — | reject if defects >= Re |
| reduced_limit | int | — | — | NORMAL rows only: max total defects of the class over the 10 counted lots |

### `batches.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| batch_id | string | BT-nnnn | — | numbered in receipt order |
| product_id | string | — | products.csv | — |
| source_id | string | — | sources.csv | — |
| rm_lot | string | RM-xx-nnnn | — | raw-material lot; batches sharing it are 'related' for hold and recall |
| lot_size | int | units | — | — |
| mfg_date | date | — | — | — |
| expiry_date | date | — | — | within shelf life while recall date <= expiry_date |

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands must be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. An empty argument (two pipes in a row) means "not supplied". Every command used in this pack:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `RECEIVE_BATCH` | `batch_id|timestamp` | Batch enters QUARANTINE |
| `SAMPLE` | `batch_id|timestamp` | Draw the sample (plan from the source's current state; doubled n for ON_HOLD; TIGHTENED for a reworked batch); refused while DISCONTINUED |
| `RECORD_RESULT` | `batch_id|timestamp|critical|major|minor` | Defects found per class -> ACCEPT (RELEASED unless short-dated) or REJECT; LATE if > 48 h after SAMPLE |
| `REWORK` | `batch_id|timestamp` | Rework a REJECTED batch (0 critical and major <= 2 x Re, once only) |
| `HOLD_REQUEST` | `batch_id|timestamp|cause_batch_id` | Put a RELEASED batch ON_HOLD because a related batch was rejected for a critical defect (<= 30 days after release) |
| `COMPLAINT` | `batch_id|timestamp|complaint_ref` | Customer complaint -> RECALLED with cascade over the RM lot |
| `CORRECTIVE_ACTION` | `source_id|timestamp|car_ref` | Lifts DISCONTINUED; inspection resumes at TIGHTENED |
| `PRINT_DECISIONS` | `` | Per-batch decisions |
| `PRINT_SWITCHING` | `source_id` | Switching-state timeline |
| `PRINT_RELEASE_REGISTER` | `` | Release / hold / recall register |

## Planted scenarios

Every edge case in the brief, mapped to the exact record where it occurs, followed by extra traps.

- **EC-01 Lot size exactly 280 (letter G) vs 281 (letter H)**
  - BT-0019: lot 280 -> code letter G; BT-0029: lot 281 -> letter H (different n / Ac / Re) — `batches.csv BT-0019 (row 19); batches.csv BT-0029 (row 29)`
- **EC-02 Defects exactly equal to Ac (accept) and exactly equal to Re (reject)**
  - BT-0018: major defects 1 = Ac (1/2, NORMAL) -> ACCEPT; BT-0044: major defects 2 = Re (1/2, NORMAL) -> REJECT — `batches.csv BT-0018 (row 18); commands.txt line 56; batches.csv BT-0044 (row 44); commands.txt line 140`
- **EC-03 Result between Ac and Re while REDUCED - accept but switch to NORMAL**
  - BT-0004 (SUP-06 starts REDUCED, see sources.csv): minor defects 3 with REDUCED Ac 2 / Re 5 -> lot ACCEPTED and RELEASED, but the source switches to NORMAL from the next batch — `batches.csv BT-0004 (row 4); commands.txt line 14; sources.csv SUP-06 (row 6)`
- **EC-04 Second rejection within 5 batches where the first was the 5th-previous batch**
  - SUP-02: rejections on BT-0022 (batch 3 of the source) and BT-0054 (batch 7) -> BT-0022 is the oldest of the 5 consecutive batches 3..7 -> 2 rejections within 5 -> TIGHTENED from batch 8. Contrast: on SUP-06 the rejections BT-0044 and BT-0087 are 5 batches apart (6 batches) -> stays NORMAL — `sources.csv SUP-02 (row 2); batches.csv BT-0022 (row 22); batches.csv BT-0054 (row 54); sources.csv SUP-06 (row 6); batches.csv BT-0044 (row 44); batches.csv BT-0087 (row 87)`
- **EC-05 Rework with major defects exactly 2 x Re**
  - BT-0030: REJECTED with 0 critical and major = 6 = exactly 2 x Re (3) -> REWORK allowed once; re-inspected at TIGHTENED (n 80, Ac 1) and accepted. Contrast BT-0070: major 7 > 2 x Re -> REWORK refused, rejection final — `batches.csv BT-0030 (row 30); commands.txt lines 99, 100, 101; batches.csv BT-0070 (row 70); commands.txt line 218`
- **EC-06 Hold request on day 30 after release vs day 31**
  - BT-0096 is rejected for a CRITICAL defect on 2026-09-11; same supplier and RM lot RM-S05-2608: BT-0073 was released 2026-08-12 (day 30) -> HOLD accepted (ON_HOLD, re-inspect with doubled sample); BT-0072 was released 2026-08-11 (day 31) -> HOLD refused — `batches.csv BT-0096 (row 96); batches.csv BT-0073 (row 73); batches.csv BT-0072 (row 72); commands.txt lines 298, 299`
- **EC-07 Recall cascade to a batch that has already expired - not recalled**
  - Re-inspection of BT-0073 (doubled sample) finds 1 critical -> RECALLED; cascade over RM lot RM-S05-2608: BT-0016 expired on 2026-08-17 -> NOT recalled; BT-0072 and line batch(es) BT-0035, BT-0045 are within shelf life -> RECALLED — `batches.csv BT-0073 (row 73); batches.csv BT-0016 (row 16); batches.csv BT-0072 (row 72); commands.txt lines 301, 302`
- **EC-08 Result recorded exactly 48 hours after sampling**
  - BT-0047 (SUP-04): result recorded exactly 48:00:00 after sampling -> on time, counts toward REDUCED; contrast BT-0031: 48 hours + 1 second -> tagged LATE (accepted, not counted) — `batches.csv BT-0047 (row 47); commands.txt line 146; batches.csv BT-0031 (row 31); commands.txt line 98`
- **Extra traps (not in the brief, but realistic):**
  - BT-0086: SUP-04 reaches 10 counted consecutive acceptances (the LATE one is skipped) within the reduced limits -> REDUCED after this batch, i.e. after the 11th accepted batch — `batches.csv BT-0086 (row 86); commands.txt line 268`
  - SUP-03: SUP-03 collected its 5th rejection while TIGHTENED -> DISCONTINUED; SAMPLE of BT-0082 must be refused until the CORRECTIVE_ACTION on line 253, after which inspection resumes at TIGHTENED — `sources.csv SUP-03 (row 3); batches.csv BT-0082 (row 82); commands.txt lines 251, 253`
  - BT-0090: accepted on inspection but only 64 of 90 shelf-life days remain at release (< 75%) -> REJECTED with reason SHORT_DATED — `batches.csv BT-0090 (row 90); commands.txt line 284`
  - BT-0001: LINE-02 is REDUCED with last batch 2026-03-20 (sources.csv); its next batch is more than 30 days later -> production irregular -> back to NORMAL before sampling — `batches.csv BT-0001 (row 1); sources.csv LINE-02 (row 8)`
  - Complaints on lines 224 and 266 recall BT-0061 and BT-0074 and cascade over their RM lots (2nd and 3rd recall triggers) — `commands.txt lines 224, 266`

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these CSV files (header row, same conventions as above, rows sorted as stated). Where the brief is silent on a format detail the choice below is binding for evaluation.

### `batch_decisions.csv`

One row per RECORD_RESULT (re-inspections are separate rows), in command order.

Columns, in order: `batch_id`, `inspection_no`, `source_state`, `code_letter`, `n_critical`, `n_major`, `n_minor`, `full_inspection`, `critical`, `major`, `minor`, `ac_major`, `re_major`, `ac_minor`, `re_minor`, `decision`, `batch_status`, `late`, `rule_ids`

### `switching_history.csv`

One row per state change, in time order.

Columns, in order: `source_id`, `timestamp`, `from_state`, `to_state`, `trigger_batch_id`, `reason`

### `release_register.csv`

One row per lifecycle event (RELEASED, REJECTED, REWORK, ON_HOLD, HOLD_REFUSED, RECALLED, NOT_RECALLED_EXPIRED, SAMPLE_REFUSED).

Columns, in order: `timestamp`, `batch_id`, `event`, `from_status`, `to_status`, `reason`, `cause_ref`

Binding choices where the brief is silent: each class uses its own (n, Ac, Re) from its AQL row; the inspector draws the largest n and every class is judged on its own Ac/Re. Switching uses the inspection decision of first inspections only (rework and hold re-inspections never count; a SHORT_DATED rejection counts as an acceptance for switching). 'Within 5 consecutive batches' = the current batch and the 4 before it in the current NORMAL spell. A LATE accepted batch is skipped for the 10-in-a-row REDUCED test (it neither counts nor breaks the run); a rejection breaks it. reduced_limit is taken from the NORMAL row of the 10th counted lot's code letter, per class. The 30-day gap is measured between consecutive RECEIVE_BATCH dates of the source and applied before sampling. Hold window: date(HOLD_REQUEST) - date(release) <= 30. Recall cascades to RELEASED/ON_HOLD batches with the same rm_lot and expiry_date >= recall date. Short-dated: (expiry_date - release date) < 0.75 x shelf_life_days. `decision` ACCEPT/REJECT; `batch_status` RELEASED, REJECTED, ON_HOLD, RECALLED; reasons e.g. CRITICAL, MAJOR_GE_RE, MINOR_GE_RE, SHORT_DATED, BETWEEN_AC_RE.
