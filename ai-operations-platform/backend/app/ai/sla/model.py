"""SLA-risk model: train, backtest, pickle, and load at runtime.

The winning pipeline from the notebook — HistGradientBoosting + isotonic
calibration over the leakage-safe features. Trained offline and pickled; the tool
loads the artifact at runtime (training lazily on first use if it is missing).
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from app.ai.sla import features as F
from app.config import get_settings

CAVEAT = (
    "SLA labels are produced by a lifecycle generator, so probabilities are "
    "illustrative and likely optimistic versus real-world signal."
)
# From the notebook's permutation-importance ranking.
TOP_DRIVERS = ["ticket_type", "sla_target_min", "priority", "metric", "queue"]


@dataclass
class SlaModel:
    pipeline: object
    categories: dict[str, list]
    metrics: dict
    drivers: list[str]
    caveat: str

    def predict_proba(self, frame: pd.DataFrame) -> np.ndarray:
        return self.pipeline.predict_proba(F.prepare_X(frame, self.categories))[:, 1]


def _new_classifier() -> CalibratedClassifierCV:
    base = HistGradientBoostingClassifier(
        categorical_features="from_dtype", random_state=0, max_iter=300, learning_rate=0.05
    )
    return CalibratedClassifierCV(base, method="isotonic", cv=3)


def _fit(frame: pd.DataFrame) -> tuple[CalibratedClassifierCV, dict]:
    categories = F.categories_from(frame)
    clf = _new_classifier().fit(F.prepare_X(frame, categories), frame[F.LABEL].values)
    return clf, categories


def _backtest(frame: pd.DataFrame) -> dict:
    ordered = frame.sort_values("created_at")
    split = ordered["created_at"].median()
    train, test = ordered[ordered["created_at"] < split], ordered[ordered["created_at"] >= split]
    clf, categories = _fit(train)
    proba = clf.predict_proba(F.prepare_X(test, categories))[:, 1]
    y = test[F.LABEL].values
    return {
        "roc_auc": round(roc_auc_score(y, proba), 3),
        "pr_auc": round(average_precision_score(y, proba), 3),
        "brier": round(brier_score_loss(y, proba), 4),
        "test_rows": int(len(test)),
    }


def train() -> SlaModel:
    frame = F.build_training_frame()
    metrics = _backtest(frame)  # honest H1/H2 numbers
    pipeline, categories = _fit(frame)  # final model on all data
    return SlaModel(pipeline=pipeline, categories=categories, metrics=metrics, drivers=TOP_DRIVERS, caveat=CAVEAT)


def model_path() -> Path:
    return get_settings().processed_dir / "models" / "sla_model.pkl"


def save(model: SlaModel, path: Path | None = None) -> Path:
    path = path or model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        pickle.dump(model, fh)
    return path


def load(path: Path | None = None) -> SlaModel:
    with open(path or model_path(), "rb") as fh:
        return pickle.load(fh)


@lru_cache(maxsize=1)
def get_model() -> SlaModel:
    """Load the pickled model; train + persist it on first use if absent."""
    path = model_path()
    if path.exists():
        return load(path)
    model = train()
    save(model, path)
    return model
