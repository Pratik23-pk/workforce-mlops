from __future__ import annotations

from pathlib import Path

import pandas as pd

from workforce_mlops.api.schemas import TimelinePoint


class TimelineService:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def load_timeline(self) -> list[TimelinePoint]:
        df = self._load_source_df()

        hires_col = "new_hires" if "new_hires" in df.columns else "target_hiring"
        layoffs_col = "layoffs" if "layoffs" in df.columns else "target_layoffs"
        net_col = "net_change" if "net_change" in df.columns else None

        grouped = (
            df.groupby("year", as_index=False)
            .agg(
                hiring=(hires_col, "sum"),
                layoffs=(layoffs_col, "sum"),
                net_change=(net_col, "sum") if net_col else (hires_col, "sum"),
            )
            .sort_values("year")
        )

        if net_col is None:
            grouped["net_change"] = grouped["hiring"] - grouped["layoffs"]

        points = [
            TimelinePoint(
                year=int(row.year),
                hiring=float(row.hiring),
                layoffs=float(row.layoffs),
                net_change=float(row.net_change),
            )
            for row in grouped.itertuples(index=False)
        ]
        return points

    def _load_source_df(self) -> pd.DataFrame:
        candidates = [
            self.project_root / "data" / "raw" / "workforce.csv",
            self.project_root / "data" / "interim" / "workforce_clean.csv",
            self.project_root / "data" / "processed" / "train.csv",
        ]

        for path in candidates:
            if path.exists():
                df = pd.read_csv(path)
                if "year" in df.columns:
                    return df

        raise FileNotFoundError("No dataset found for timeline graph")
