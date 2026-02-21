from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from workforce_mlops.config import REQUIRED_COLUMNS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate dataset schema")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--report", required=True, help="Validation report JSON path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    report_path = Path(args.report)

    df = pd.read_csv(in_path)
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]

    report = {
        "rows": int(df.shape[0]),
        "columns": int(df.shape[1]),
        "missing_columns": missing_cols,
        "null_counts": {k: int(v) for k, v in df.isnull().sum().to_dict().items()},
        "valid": len(missing_cols) == 0,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if missing_cols:
        raise ValueError(f"Validation failed. Missing columns: {missing_cols}")

    print(f"Validation passed. Report saved to {report_path}")


if __name__ == "__main__":
    main()
