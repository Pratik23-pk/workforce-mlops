from __future__ import annotations

import torch

from workforce_mlops.models.multitask_model import MultiTaskNet


def test_multitask_forward_shapes() -> None:
    model = MultiTaskNet(input_dim=10, hidden_dims=[16, 8], dropout=0.1)
    x = torch.randn(4, 10)
    out = model(x)

    assert out["hiring"].shape == (4,)
    assert out["layoffs"].shape == (4,)
    assert out["layoff_risk_logits"].shape == (4,)
    assert out["workforce_volatility"].shape == (4,)
