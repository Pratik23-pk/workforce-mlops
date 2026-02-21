from __future__ import annotations

import pandas as pd

from workforce_mlops.data.preprocess import add_targets


def test_add_targets_creates_expected_columns() -> None:
    df = pd.DataFrame(
        {
            "employees_start": [100, 200],
            "new_hires": [10, 20],
            "layoffs": [15, 5],
            "is_estimated": [True, False],
        }
    )

    out = add_targets(df, layoff_risk_threshold=0.1)

    assert "target_hiring" in out
    assert "target_layoffs" in out
    assert "target_layoff_risk" in out
    assert "target_workforce_volatility" in out
    assert out["target_layoff_risk"].tolist() == [1, 0]
