
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

    print("\nCommand execution completed.")


if __name__ == "__main__":
    main()
