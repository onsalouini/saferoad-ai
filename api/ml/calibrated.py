# api/ml/calibrated.py
"""Modèle LightGBM + recalibration de Platt (régression logistique sur le logit brut)."""
from __future__ import annotations

import numpy as np


class CalibratedClassifier:
    """
    Même interface que LGBMClassifier pour l'API :
    - predict_proba -> probabilités recalibrées ;
    - predict(..., pred_contrib=True) -> contributions SHAP du modèle brut (log-odds) ;
    - booster_ / get_params -> ceux du modèle brut.
    """

    def __init__(self, model, a: float, b: float) -> None:
        self.model = model
        self.a = float(a)  # p = sigmoïde(a * logit_brut + b)
        self.b = float(b)

    def raw_logit(self, X) -> np.ndarray:
        return self.model.predict(X, raw_score=True)

    def predict_proba(self, X) -> np.ndarray:
        p = 1.0 / (1.0 + np.exp(-(self.a * self.raw_logit(X) + self.b)))
        return np.column_stack([1 - p, p])

    def predict(self, X, **kwargs):
        return self.model.predict(X, **kwargs)

    @property
    def booster_(self):
        return self.model.booster_

    def get_params(self, deep: bool = True) -> dict:
        return self.model.get_params(deep)
