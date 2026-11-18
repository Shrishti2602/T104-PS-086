
# T104 – PS-086 Decision Log

This document records the important technical decisions made during development of the AQL Sampling, Inspection Severity and Batch Release Engine.

| No. | Decision | Reason |
|---|---|---|
| 1 | Use Python 3.10+ | Python supports modular development, CSV processing and automated testing. |
| 2 | Use CSV files for input data | CSV provides a simple and structured format for products, suppliers, batches and sampling rules. |
| 3 | Use a modular architecture | Separating sampling, inspection, switching and lifecycle logic improves maintainability and testing. |
| 4 | Use a command-file-driven interface | This follows the assignment requirement of operating without a graphical user interface. |
| 5 | Use separate AQL rules for critical, major and minor defects | Each defect class must be evaluated against its own acceptance and rejection limits. |
| 6 | Use Pytest for automated testing | Automated tests help verify business rules and edge cases consistently. |
| 7 | Use Git and GitHub for version control | Version control tracks code changes and enables collaboration between team members. |
| 8 | Maintain separate decision, switching and release records | Separate reports provide traceability for inspection decisions and batch lifecycle events. |
| 9 | Record inspection timing and late results | The system must enforce the 48-hour result rule and exclude late results from the reduced-inspection acceptance streak. |
| 10 | Validate changes using the complete test suite | Running the full test suite helps detect regressions after code changes. |

## Development Notes

- Programming language selected: Python.
- Repository: https://github.com/Shrishti2602/T104-PS-086
- Latest recorded test result: 82 tests passed (18 November 2026).
- Latest recorded project fix: automatic recall after a critical defect during hold reinspection.
- The supplied 382-command sample dataset has been executed and its three output reports have been validated. Final documentation, packaging and demonstration preparation remain.

## Future Updates

New decisions, changes to business-rule interpretations, test findings and design improvements should be added here with their dates and reasons.

| 11 | Record business-rule references in inspection decisions | Improves traceability between inspection results and the applicable business rules. |
| 12 | Preserve ON_HOLD to RECALLED as a direct lifecycle transition for critical hold-reinspection defects | Keeps the release register consistent with the actual batch lifecycle while retaining the REJECT inspection decision. |
| 13 | Validate the complete supplied command stream and generated reports | Checks integration behaviour across the supplied scenarios in addition to individual unit tests. |
