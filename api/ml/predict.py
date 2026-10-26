# api/ml/predict.py
"""Chargement du modèle LightGBM, prédiction et explication (contributions SHAP)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib
import numpy as np

from .features import GROUP_LABELS, build_row, group_contributions, to_frame

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(os.getenv("MODEL_PATH", ROOT / "ml" / "models" / "saferoad_model.pkl"))
REPORT_PATH = ROOT / "ml" / "reports" / "evaluation.json"
TRAINING_PATH = ROOT / "ml" / "reports" / "training.json"

# Niveaux de risque : libellés et conseils ; les bornes viennent du modèle (v3) ou des valeurs v2
LEVEL_TEXT = {
    "critical": ("Très élevé", "Risque très élevé : départ fortement déconseillé dans ces conditions."),
    "serious": ("Élevé", "Conditions dangereuses : envisagez un autre horaire ou itinéraire."),
    "warning": ("Modéré", "Quelques facteurs de risque : prudence recommandée."),
    "good": ("Faible", "Conditions favorables, aucun facteur de risque marqué."),
}
DEFAULT_LEVELS = {"warning": 0.40, "serious": 0.65, "critical": 0.80}


class ModelService:
    def __init__(self) -> None:
        self.model = None
        self.feature_names: list[str] = []
        self.thresholds = {"standard": 0.65, "pro": 0.75, "strict": 0.85}
        self.level_bounds = dict(DEFAULT_LEVELS)
        self.version = "2.0"
        self.calibrated = False
        self.roc_auc: float | None = None
        self.error: str | None = None
        self.load()

    @staticmethod
    def _download() -> None:
        """Déploiement : télécharge le modèle depuis MODEL_URL s'il n'est pas présent sur le disque."""
        url = os.getenv("MODEL_URL")
        if MODEL_PATH.exists() or not url:
            return
        import urllib.request

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = MODEL_PATH.with_suffix(".part")
        print(f"Téléchargement du modèle : {url}")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(MODEL_PATH)

    def load(self) -> None:
        try:
            self._download()
            data = joblib.load(MODEL_PATH)
            self.model = data["model"]
            self.feature_names = list(data["feature_names"])
            self.thresholds = {
                "standard": float(data.get("threshold_standard", 0.65)),
                "pro": float(data.get("threshold_pro", 0.75)),
                "strict": float(data.get("threshold_strict", 0.85)),
            }
            self.level_bounds = {k: float(v) for k, v in (data.get("levels") or DEFAULT_LEVELS).items()}
            self.version = str(data.get("version", "2.0"))
            self.calibrated = bool(data.get("calibrated", False))
            self.roc_auc = data.get("roc_auc")
            print(f"Modele charge : {len(self.feature_names)} variables ({MODEL_PATH})")
        except Exception as e:  # noqa: BLE001
            self.error = f"{type(e).__name__}: {e}"
            print(f"ERREUR chargement du modele : {self.error}")

    @property
    def ready(self) -> bool:
        return self.model is not None

    # ------------------------------------------------------------------ core
    def probabilities(self, situations: list[dict]) -> np.ndarray:
        df = to_frame([build_row(s) for s in situations], self.feature_names)
        return self.model.predict_proba(df)[:, 1]

    def contributions(self, situation: dict) -> tuple[float, dict[str, float]]:
        df = to_frame([build_row(situation)], self.feature_names)
        contrib = self.model.predict(df, pred_contrib=True)[0]
        base = float(contrib[-1])
        return base, group_contributions(contrib[:-1], self.feature_names)

    # --------------------------------------------------------------- helpers
    def level(self, proba: float) -> dict:
        status = "good"
        for name in ("warning", "serious", "critical"):
            if proba >= self.level_bounds[name]:
                status = name
        label, text = LEVEL_TEXT[status]
        return {"label": label, "status": status, "advice": text}

    def assess(self, proba: float, mode: str, threshold: float | None = None) -> dict:
        """threshold : seuil d'alerte imposé (profils de conducteur) ; sinon celui du mode."""
        if threshold is None:
            threshold = self.thresholds.get(mode, self.thresholds["standard"])
        lvl = self.level(proba)
        return {
            "probability": round(float(proba), 4),
            "risk_score": round(float(proba) * 100, 1),
            "risk_level": lvl["label"],
            "status": lvl["status"],
            "advice": lvl["advice"],
            "mode": mode,
            "threshold_used": threshold,
            "is_high_risk": bool(proba >= threshold),
        }

    def explain(self, situation: dict, top: int = 8) -> dict:
        base, groups = self.contributions(situation)
        # Distance(mi) est fixe à l'inférence : sa contribution est un décalage constant,
        # pas un facteur propre à la situation -> intégrée à la valeur de base.
        base += groups.pop("Distance(mi)", 0.0)  # modèles v2 uniquement
        items = sorted(groups.items(), key=lambda kv: abs(kv[1]), reverse=True)
        factors = [
            {
                "feature": k,
                "label": GROUP_LABELS.get(k, k),
                "impact": round(v, 4),
                "direction": "hausse" if v > 0 else "baisse",
            }
            for k, v in items[:top]
            if abs(v) > 1e-4
        ]
        return {"base_logit": round(base, 4), "factors": factors}

    def predict_one(self, situation: dict, mode: str = "standard") -> dict:
        proba = float(self.probabilities([situation])[0])
        out = self.assess(proba, mode)
        out["explanation"] = self.explain(situation)
        return out

    def info(self) -> dict:
        importances = []
        if self.ready:
            gain = self.model.booster_.feature_importance(importance_type="gain")
            groups: dict[str, float] = {}
            from .features import feature_group

            for g, col in zip(gain, self.feature_names):
                key = feature_group(col)
                groups[key] = groups.get(key, 0.0) + float(g)
            total = sum(groups.values()) or 1.0
            importances = [
                {"feature": k, "label": GROUP_LABELS.get(k, k), "share": round(v / total, 4)}
                for k, v in sorted(groups.items(), key=lambda kv: kv[1], reverse=True)
            ]
        report = None
        if REPORT_PATH.exists():
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        training = None
        if TRAINING_PATH.exists() and self.calibrated:
            training = json.loads(TRAINING_PATH.read_text(encoding="utf-8"))
        params = self.model.get_params() if self.ready else {}
        return {
            "ready": self.ready,
            "error": self.error,
            "algorithm": "LGBMClassifier + recalibration de Platt" if self.calibrated else (type(self.model).__name__ if self.ready else None),
            "version": self.version,
            "calibrated": self.calibrated,
            "levels": self.level_bounds,
            "n_features": len(self.feature_names),
            "declared_roc_auc": self.roc_auc,
            "thresholds": self.thresholds,
            "hyperparameters": {
                k: params.get(k)
                for k in ("n_estimators", "learning_rate", "num_leaves", "max_depth",
                          "min_child_samples", "subsample", "colsample_bytree", "scale_pos_weight")
            },
            "feature_importance": importances,
            "evaluation": report,
            "training": training,
        }


model_service = ModelService()
