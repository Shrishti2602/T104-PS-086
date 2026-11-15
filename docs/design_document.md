# T104 – PS-086
# AQL Sampling, Inspection Severity and Batch Release Engine

## 1. Project Information

| Item | Details |
|---|---|
| Organisation | 10 SECONDS |
| Team ID | T104 |
| Problem Statement | PS-086 |
| Project Title | AQL Sampling, Inspection Severity and Batch Release Engine |
| Domain | Manufacturing – Quality |
| Programming Language | Python 3.10+ |
| Team Member 1 | Shreya Y H – 1AT24IS183 |
| Team Member 2 | Shrishti – 1AT24IS184 |

## 2. Introduction

The AQL Sampling, Inspection Severity and Batch Release Engine is a command-file-driven quality management system.

It helps manufacturers inspect incoming or production batches using Acceptance Quality Limit (AQL) sampling rules. The system calculates sample sizes, evaluates critical, major and minor defects, decides whether batches should be accepted or rejected, and maintains supplier inspection severity.

It also manages rework, batch holds, release restrictions and product recalls.

## 3. Project Objectives

1. Calculate sample sizes using lot-size bands and sampling tables.
2. Evaluate each defect class independently.
3. Make ACCEPT or REJECT decisions using Ac and Re values.
4. Maintain supplier inspection states.
5. Support rework and hold reinspection.
6. Manage recalls and recall cascades.
7. Enforce shelf-life and result-timing requirements.
8. Maintain decision history, switching history and release registers.
9. Produce accurate reports for evaluation.

## 4. Technology Stack

- Python 3.10+
- CSV files for input and output data
- Pytest for unit testing
- Git and GitHub for version control
- Command-line interface for command execution

## 5. System Architecture

The system is divided into the following modules:

1. Master Data Module – loads products, suppliers and batches.
2. Data Loader Module – reads CSV files and sampling rules.
3. Sampling Module – calculates sample sizes and acceptance limits.
4. Inspection Module – evaluates defects and inspection decisions.
5. Switching Module – manages NORMAL, TIGHTENED, REDUCED and DISCONTINUED states.
6. Engine Module – coordinates inspection and batch lifecycle operations.
7. Command Processor – interprets and executes input commands.
8. Reporting Module – maintains decision, switching and release records.

### Architecture Diagram

```text
             INPUT CSV FILES
                    |
                    v
             DATA LOADER
                    |
                    v
              MASTER DATA
                    |
                    v
           COMMAND PROCESSOR
                    |
                    v
             QUALITY ENGINE
                    |
          +---------+---------+
          |         |         |
          v         v         v
       SAMPLING  INSPECTION SWITCHING
          |         |         |
          +---------+---------+
                    |
                    v
             BATCH LIFECYCLE
                    |
          +---------+---------+
          |         |         |
          v         v         v
       DECISION  SWITCHING  RELEASE
        REPORT    HISTORY  REGISTER
```

## 6. Main Entities

### Product
- product_id
- product_name
- critical AQL
- major AQL
- minor AQL
- shelf-life information

### Supplier / Production Line
- source_id
- source_name
- current inspection state
- inspection history
- corrective action information

### Batch
- batch_id
- product_id
- source_id
- lot_size
- raw-material lot
- manufacturing date
- expiry date
- current status

### Sampling Rule
- code_letter
- AQL
- severity
- sample_size
- acceptance number (Ac)
- rejection number (Re)
- reduced_limit

### Inspection Decision
- batch_id
- inspection number
- sample size
- defects found
- decision
- batch status
- timing information
- applicable rule IDs

## 7. Entity Relationships

```text
PRODUCT
   |
   | 1 to many
   v
BATCH -------- SUPPLIER / LINE
   |                  |
   |                  | 1 to many
   v                  v
INSPECTION         SWITCHING
DECISION           HISTORY
   |
   v
RELEASE REGISTER

SAMPLING TABLE
      |
      v
  SAMPLING PLAN
      |
      v
  INSPECTION
```

A product can have multiple batches. A supplier or production line can provide multiple batches. Each batch can have multiple inspection records. Each inspection uses sampling rules applicable to the batch's lot size, AQL and current inspection state.

## 8. Business Rules

### BR-01: Lot Size and Sample Size Selection
Determine the code letter from the configured lot-size bands and retrieve the appropriate sample size and Ac/Re values from the sampling table.

### BR-02: Per-Class Defect Evaluation
Evaluate critical, major and minor defects independently against their respective AQL rules. Reject the batch if any class reaches its Re value. A critical defect count of at least one always causes rejection.

### BR-03: Full Inspection
If the calculated sample size is greater than or equal to the lot size, inspect the entire lot. Apply the supplied acceptance and rejection numbers.

### BR-04: NORMAL to TIGHTENED
Move the supplier or production line from NORMAL to TIGHTENED after two rejections within five consecutive batches.

### BR-05: TIGHTENED to NORMAL
Return to NORMAL after five consecutive acceptances while in TIGHTENED state.

### BR-06: TIGHTENED to DISCONTINUED
Move to DISCONTINUED after five rejections while in TIGHTENED state. Rejections are cumulative, not necessarily consecutive.

### BR-07: NORMAL to REDUCED
Move to REDUCED after ten consecutive acceptances when total defects remain within the applicable reduced-limit values.

### BR-08: REDUCED to NORMAL
Return to NORMAL if a rejection occurs, a result falls between Ac and Re, or production irregularity occurs due to a gap exceeding 30 days.

### BR-09: DISCONTINUED Corrective Action
Do not inspect new batches while the source is DISCONTINUED. After a corrective action record is logged, resume inspection in TIGHTENED state.

### BR-10: Rework
A rejected batch may be reworked once if critical defects are zero and major defects do not exceed twice the applicable Re value. Reinspect using a new sample under TIGHTENED inspection. A second rejection is final.

### BR-11: Hold
A released batch may be placed ON_HOLD within 30 days of release if a related batch from the same supplier and raw-material lot is later rejected for a critical defect. Reinspect held batches using double the sample size.

### BR-12: Recall
A critical defect during ON_HOLD reinspection or a customer complaint citing a batch triggers recall. Recall cascades to batches sharing the same raw-material lot that have not expired at the recall date.

### BR-13: Shelf-Life Release Restriction
A batch cannot be released if its remaining shelf life is less than 75% of its total shelf life. Such a batch is rejected with reason SHORT_DATED.

### BR-14: Inspection Result Timing
Inspection results must be recorded within 48 hours of sampling. Later results are accepted but tagged LATE and excluded from the REDUCED-state ten-consecutive-acceptances calculation.

## 9. Batch Lifecycle

The expected lifecycle includes:

```text
QUARANTINE
     |
     v
UNDER_INSPECTION
     |
     +--------------------+
     |                    |
     v                    v
  RELEASED              REJECTED
     |                    |
     v                    v
  ON_HOLD              REWORK
     |                    |
     v                    v
  REINSPECTION       REINSPECTION
     |
     v
  RECALLED
```

Only valid lifecycle transitions are permitted. Recall and rejection conditions must be enforced by the quality engine.

## 10. Inspection Severity Switching

The system supports four inspection states:

- NORMAL – standard inspection.
- TIGHTENED – stricter inspection after repeated rejections.
- REDUCED – reduced inspection after sustained acceptable results.
- DISCONTINUED – inspection stopped until corrective action is recorded.

A result between Ac and Re is accepted because it has not reached the rejection number. However, under REDUCED inspection, this result triggers a return to NORMAL because it does not satisfy the reduced-inspection continuation condition.

## 11. Reports and Output Files

The project maintains three required CSV reports.

### batch_decisions.csv

Contains one row per RECORD_RESULT, including reinspection results.

Required fields:

batch_id, inspection_no, source_state, code_letter, n_critical, n_major, n_minor, full_inspection, critical, major, minor, ac_major, re_major, ac_minor, re_minor, decision, batch_status, late, rule_ids

### switching_history.csv

Contains one row per inspection-state transition in chronological order.

Required fields:

source_id, timestamp, from_state, to_state, trigger_batch_id, reason

### release_register.csv

Contains one row per lifecycle event.

Required fields:

timestamp, batch_id, event, from_status, to_status, reason, cause_ref

## 12. Testing Strategy

The project uses Pytest for automated testing.

Testing covers:

- Lot-size boundary conditions.
- Acceptance and rejection boundaries.
- Defect classification.
- Inspection severity switching.
- Rework eligibility.
- Hold eligibility and reinspection.
- Recall cascades.
- Shelf-life restrictions.
- Result timing.
- Command parsing and execution.
- Report generation.

The current test suite has passed 68 tests. Further tests and validation will be performed as the implementation is completed.

## 13. Development and Version Control

The project is maintained in GitHub.

Repository:
https://github.com/Shrishti2602/T104-PS-086

The implementation is developed and validated using Python and Pytest. Changes are committed to the main branch after testing.

## 14. Conclusion

The AQL Sampling, Inspection Severity and Batch Release Engine provides a structured approach to manufacturing quality inspection. It combines acceptance sampling, supplier inspection switching, batch lifecycle management and traceable reporting.

The system is designed to make consistent quality decisions and support reliable batch release and recall operations.
