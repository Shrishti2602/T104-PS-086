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

        print(f"Report exported: {filename} ({len(records)} rows)")




def main():
    print("Loading project data...")

    products = load_products(DATA_DIR / "products.csv")
    sources = load_sources(DATA_DIR / "sources.csv")
    batches = load_batches(
        DATA_DIR / "batches.csv",
        products,
        sources,
    )
    bands = load_lot_size_bands(DATA_DIR / "lot_size_bands.csv")
    rules = load_sampling_table(DATA_DIR / "sampling_table.csv")

    print(f"Products loaded: {len(products)}")
    print(f"Sources loaded: {len(sources)}")
    print(f"Batches loaded: {len(batches)}")
    print(f"Lot-size bands loaded: {len(bands)}")
    print(f"Sampling rules loaded: {len(rules)}")

    engine = BatchEngine(
        products,
        sources,
        batches,
        bands,
        rules,
    )

    processor = CommandProcessor(engine)

    print("\nExecuting commands...")
    results = processor.execute_file(DATA_DIR / "commands.txt")

    print(f"Commands executed: {len(results)}")
    print(f"Inspection decisions: {len(engine.batch_decisions)}")
    print(f"Lifecycle events: {len(engine.release_register)}")
    print(f"Switching transitions: {len(engine.switching_history)}")
    print(f"Print requests: {len(processor.print_requests)}")
    print("\nExporting reports...")
    export_reports(engine)

    print("\nCommand execution and report export completed.")


if __name__ == "__main__":
    main()
