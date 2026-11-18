
import csv
from pathlib import Path

from quality_engine.data_loader import (
    load_lot_size_bands,
    load_sampling_table,
)
from quality_engine.master_data import (
    load_products,
    load_sources,
    load_batches,
)
from quality_engine.engine import BatchEngine
from quality_engine.command_processor import CommandProcessor


PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"


def print_table(title, headers, rows):
    """Print information in a clean terminal table."""

    rows = [[str(value) for value in row] for row in rows]

    widths = [
        max(
            len(str(header)),
            max((len(row[i]) for row in rows), default=0),
        )
        for i, header in enumerate(headers)
    ]

    total_width = sum(widths) + 3 * (len(headers) - 1)

    print(f"\n{title}")
    print("=" * total_width)

    header_line = " | ".join(
        str(header).ljust(widths[i])
        for i, header in enumerate(headers)
    )
    print(header_line)
    print("-" * total_width)

    for row in rows:
        print(
            " | ".join(
                row[i].ljust(widths[i])
                for i in range(len(headers))
            )
        )

    print("=" * total_width)


def export_reports(engine):
    """Export inspection, switching and lifecycle reports to CSV."""

    reports = {
        "batch_decisions.csv": (
            [
                "batch_id", "inspection_no", "source_state",
                "code_letter", "n_critical", "n_major", "n_minor",
                "full_inspection", "critical", "major", "minor",
                "ac_major", "re_major", "ac_minor", "re_minor",
                "decision", "batch_status", "late", "rule_ids",
            ],
            engine.batch_decisions,
        ),
        "switching_history.csv": (
            [
                "source_id", "timestamp", "from_state", "to_state",
                "trigger_batch_id", "reason",
            ],
            engine.switching_history,
        ),
        "release_register.csv": (
            [
                "timestamp", "batch_id", "event", "from_status",
                "to_status", "reason", "cause_ref",
            ],
            engine.release_register,
        ),
    }

    report_summary = []

    for filename, (fieldnames, records) in reports.items():
        with (PROJECT_ROOT / filename).open(
            "w", newline="", encoding="utf-8"
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()
            writer.writerows(records)

        report_summary.append((filename, len(records)))

    return report_summary


def main():
    print("\n" + "=" * 60)
    print("       AQL SAMPLING AND BATCH RELEASE ENGINE")
    print("=" * 60)

    print("\nLoading project data...")

    products = load_products(DATA_DIR / "products.csv")
    sources = load_sources(DATA_DIR / "sources.csv")
    batches = load_batches(
        DATA_DIR / "batches.csv",
        products,
        sources,
    )
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")
    rules = load_sampling_table(DATA_DIR / "sampling_table.csv")

    print_table(
        "PROJECT DATA LOADED",
        ["Data", "Records"],
        [
            ("Products", len(products)),
            ("Sources", len(sources)),
            ("Batches", len(batches)),
            ("Lot-size bands", len(bands)),
            ("Sampling rules", len(rules)),
        ],
    )

    engine = BatchEngine(
        products,
        sources,
        batches,
        bands,
        rules,
    )

    processor = CommandProcessor(engine)

    print("\nExecuting inspection commands...")
    results = processor.execute_file(DATA_DIR / "commands.txt")

    print_table(
        "EXECUTION SUMMARY",
        ["Result", "Count"],
        [
            ("Commands executed", len(results)),
            ("Inspection decisions", len(engine.batch_decisions)),
            ("Lifecycle events", len(engine.release_register)),
            ("Switching transitions", len(engine.switching_history)),
            ("Print requests", len(processor.print_requests)),
        ],
    )

    print("\nExporting reports...")
    report_summary = export_reports(engine)

    print_table(
        "GENERATED CSV REPORTS",
        ["Report file", "Records"],
        report_summary,
    )

    print("\n" + "=" * 60)
    print("       PROJECT EXECUTION COMPLETED SUCCESSFULLY")
    print("=" * 60)


if __name__ == "__main__":
    main()
