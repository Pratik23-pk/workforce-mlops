from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn

from workforce_mlops.models.multitask_model import MultiTaskNet


class ResidualBlock(nn.Module):
    def __init__(self, dim: int, dropout: float) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
        )
        self.act = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.act(x + self.net(x))


class ResidualMultiTaskNet(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 128, dropout: float = 0.2) -> None:
        super().__init__()
        self.input = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
        )
        self.block1 = ResidualBlock(hidden_dim, dropout)
        self.block2 = ResidualBlock(hidden_dim, dropout)

        self.hiring_head = nn.Linear(hidden_dim, 1)
        self.layoffs_head = nn.Linear(hidden_dim, 1)
        self.layoff_risk_head = nn.Linear(hidden_dim, 1)
        self.volatility_head = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        z = self.input(x)
        z = self.block1(z)
        z = self.block2(z)
        return {
            "hiring": self.hiring_head(z).squeeze(-1),
            "layoffs": self.layoffs_head(z).squeeze(-1),
            "layoff_risk_logits": self.layoff_risk_head(z).squeeze(-1),
            "workforce_volatility": self.volatility_head(z).squeeze(-1),
        }


class WideDeepMultiTaskNet(nn.Module):
    """Linear shortcut path plus nonlinear deep tower."""

    def __init__(self, input_dim: int, hidden_dims: list[int], dropout: float) -> None:
        super().__init__()
        if not hidden_dims:
            raise ValueError("hidden_dims must contain at least one layer for wide-deep model")

        layers: list[nn.Module] = []
        prev = input_dim
        for dim in hidden_dims:
            layers.extend([nn.Linear(prev, dim), nn.ReLU(), nn.Dropout(dropout)])
            prev = dim
        self.deep_tower = nn.Sequential(*layers)

        self.wide_hiring = nn.Linear(input_dim, 1)
        self.wide_layoffs = nn.Linear(input_dim, 1)
        self.wide_risk = nn.Linear(input_dim, 1)
        self.wide_volatility = nn.Linear(input_dim, 1)

        self.deep_hiring = nn.Linear(prev, 1)
        self.deep_layoffs = nn.Linear(prev, 1)
        self.deep_risk = nn.Linear(prev, 1)
        self.deep_volatility = nn.Linear(prev, 1)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        z = self.deep_tower(x)
        return {
            "hiring": (self.wide_hiring(x) + self.deep_hiring(z)).squeeze(-1),
            "layoffs": (self.wide_layoffs(x) + self.deep_layoffs(z)).squeeze(-1),
            "layoff_risk_logits": (self.wide_risk(x) + self.deep_risk(z)).squeeze(-1),
            "workforce_volatility": (self.wide_volatility(x) + self.deep_volatility(z)).squeeze(-1),
        }


def _normalize_hidden_dims(hidden_dims: Sequence[int] | list[int]) -> list[int]:
    if not hidden_dims:
        return [128, 64]
    return [int(v) for v in hidden_dims]


def build_model(
    model_kind: str,
    input_dim: int,
    hidden_dims: Sequence[int] | list[int],
    dropout: float,
) -> nn.Module:
    kind = str(model_kind).strip().lower()
    dims = _normalize_hidden_dims(hidden_dims)

    if kind in {"mlp", "baseline_mlp"}:
        return MultiTaskNet(input_dim=input_dim, hidden_dims=dims, dropout=dropout)
    if kind in {"wide_deep", "wide_deep_mlp"}:
        return WideDeepMultiTaskNet(input_dim=input_dim, hidden_dims=dims, dropout=dropout)
    if kind in {"residual", "residual_mlp"}:
        return ResidualMultiTaskNet(input_dim=input_dim, hidden_dim=dims[0], dropout=dropout)

    raise ValueError(f"Unknown model kind: {model_kind}")
