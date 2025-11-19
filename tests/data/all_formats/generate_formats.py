#!/usr/bin/env python3
"""Generate test files in all supported formats."""

from pathlib import Path

import pandas as pd

base_dir = Path(__file__).parent

# Define formats: (extension, writer_func, optional_dep_name)
formats = [
    ("tsv", lambda df, p: df.to_csv(p, sep="\t", index=False), None),
    ("parquet", lambda df, p: df.to_parquet(p, index=False), "pyarrow"),
    ("feather", lambda df, p: df.to_feather(p), "pyarrow"),
    ("json", lambda df, p: df.to_json(p, orient="records", indent=2), None),
    ("jsonl", lambda df, p: df.to_json(p, orient="records", lines=True), None),
    ("xlsx", lambda df, p: df.to_excel(p, index=False, engine="openpyxl"), "openpyxl"),
    ("orc", lambda df, p: df.to_orc(p, index=None), "pyarrow"),
    ("xml", lambda df, p: df.to_xml(p, index=False), "lxml"),
    ("pkl", lambda df, p: df.to_pickle(p), None),
]

for dataset in ["location", "sensor"]:
    df = pd.read_csv(base_dir / f"{dataset}.csv")
    print(f"Generating {dataset} files...")

    for ext, writer, dep in formats:
        filepath = base_dir / f"{dataset}.{ext}"
        try:
            writer(df, filepath)
            print(f"  ✓ {dataset}.{ext}")
        except (ImportError, ValueError):
            print(f"  ✗ {dataset}.{ext} (missing {dep})")

print("\n✓ Format generation complete!")
