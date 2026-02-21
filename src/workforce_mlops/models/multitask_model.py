from __future__ import annotations

import torch
from torch import nn


class MultiTaskNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dims: list[int], dropout: float = 0.2) -> None:
        super().__init__()

        layers: list[nn.Module] = []
        current_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(current_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ]
            )
            current_dim = hidden_dim

        self.shared = nn.Sequential(*layers)

        self.hiring_head = nn.Linear(current_dim, 1)
        self.layoffs_head = nn.Linear(current_dim, 1)
        self.layoff_risk_head = nn.Linear(current_dim, 1)
        self.volatility_head = nn.Linear(current_dim, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        z = self.shared(x)
        return {
            "hiring": self.hiring_head(z).squeeze(-1),
            "layoffs": self.layoffs_head(z).squeeze(-1),
            "layoff_risk_logits": self.layoff_risk_head(z).squeeze(-1),
            "workforce_volatility": self.volatility_head(z).squeeze(-1),
        }
