from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest workforce dataset")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output cleaned CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)

    df = pd.read_csv(in_path)
    df = df.drop_duplicates().reset_index(drop=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    print(f"Ingested {len(df)} rows -> {out_path}")


if __name__ == "__main__":
    main()
