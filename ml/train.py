"""
Réentraînement du modèle SafeRoad AI (v4).

Par rapport à la v2 / v3 (voir ml/reports/EVALUATION.md) :
  1. Distance(mi) retirée (fuite de données : longueur impactée PAR l'accident) ;
  2. Découpage temporel : entraînement avant TEST_FROM, test sur les années suivantes ;
  3. Probabilités recalibrées (Platt) sur un jeu de calibration séparé ;
  4. (v4) Type de route (autoroute / route / rue) déduit du nom de la rue ;
  5. (v4) Contraintes monotones : plus de pluie, moins de visibilité, nuit, brouillard ou neige
     ne peuvent jamais faire BAISSER le score ;
  6. (v4) Échantillon de tous les fragments du dataset (toutes les années) et petite recherche
     d'hyperparamètres.

Usage :
    python ml/train.py                              # tous les data/raw/shard*.parquet
    python ml/train.py --per-shard 300000 --trials 6

Produit ml/models/saferoad_model.pkl (le précédent est sauvegardé en saferoad_model_v<version>.pkl)
et ml/reports/training.json.
"""
from __future__ import annotations

import argparse
import gc
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, early_stopping, log_evaluation
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "ml"))
from evaluate import calibration, engineer, load  # noqa: E402
from ml.calibrated import CalibratedClassifier  # noqa: E402
from ml.features import ROAD_CLASS_FEATURES  # noqa: E402

MODEL_PATH = ROOT / "ml" / "models" / "saferoad_model.pkl"
REPORT_PATH = ROOT / "ml" / "reports" / "training.json"
TEST_FROM = 2022
# Rappels visés par mode (mêmes compromis que la v2 : 80 % / 66 % / 42 %)
RECALL_TARGETS = {"standard": 0.80, "pro": 0.66, "strict": 0.42}
RECALL_MODERATE = 0.92  # borne basse du niveau « Modéré »

# +1 : la variable ne peut que faire monter le score ; -1 : que le faire baisser.
# Seuls les effets physiquement établis sont contraints ; heure de pointe et vent restent libres.
MONOTONE = {
    "Precipitation(in)": 1,
    "Visibility(mi)": -1,
    "Sunrise_Sunset": 1,  # nuit = 1
    "Weather_Condition_Heavy Rain": 1,
    "Weather_Condition_Rain": 1,
    "Weather_Condition_Light Rain": 1,
    "Weather_Condition_Light Snow": 1,
    "Weather_Condition_Fog": 1,
}

SEARCH_SPACE = {
    "num_leaves": [63, 127, 255],
    "max_depth": [8, 10, 12],
    "min_child_samples": [20, 50, 100],
    "colsample_bytree": [0.6, 0.8, 1.0],
    "reg_lambda": [0.0, 1.0, 5.0],
}


def threshold_for_recall(y: np.ndarray, p: np.ndarray, recall: float) -> float:
    prec, rec, thr = precision_recall_curve(y, p)
    # rec est décroissant ; on prend le seuil le plus haut qui atteint encore le rappel visé
    ok = np.where(rec[:-1] >= recall)[0]
    return float(thr[ok[-1]]) if len(ok) else float(thr[0])


def metrics(y, p) -> dict:
    return {
        "roc_auc": round(float(roc_auc_score(y, p)), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 4),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "mean_predicted": round(float(p.mean()), 4),
        "positive_rate": round(float(y.mean()), 4),
    }


def load_all(paths: list[Path], per_shard: int) -> pd.DataFrame:
    frames = []
    for path in paths:
        df = load(str(path), per_shard)
        print(f"  {path.name} : {len(df):,} lignes")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="*", help="fichiers parquet (défaut : data/raw/shard*.parquet)")
    ap.add_argument("--per-shard", type=int, default=300_000, help="lignes tirées par fragment (limite mémoire)")
    ap.add_argument("--trees", type=int, default=3000)
    ap.add_argument("--trials", type=int, default=6, help="essais de la recherche d'hyperparamètres (0 = aucun)")
    args = ap.parse_args()

    old = joblib.load(MODEL_PATH)
    feats = [f for f in old["feature_names"] if f not in ("Distance(mi)", *ROAD_CLASS_FEATURES)] + ROAD_CLASS_FEATURES

    paths = [Path(p) for p in args.data] if args.data else sorted((ROOT / "data" / "raw").glob("shard*.parquet"))
    print(f"Chargement de {len(paths)} fragment(s)")
    df = load_all(paths, args.per_shard)
    y_all = (df["Severity"] >= 3).astype(np.int8).to_numpy()
    X_all = engineer(df, feats, night_is_one=True).astype(np.float32)
    years = df["Year"].to_numpy()
    print(f"{len(df):,} accidents ; années : {sorted(set(years.tolist()))}")

    test = years >= TEST_FROM
    rng = np.random.default_rng(42)
    split = rng.random(len(df))
    fit = ~test & (split < 0.8)
    valid = ~test & (split >= 0.8) & (split < 0.9)   # arrêt précoce et choix des hyperparamètres
    calib = ~test & (split >= 0.9)                    # recalibration et seuils
    monotone = [MONOTONE.get(f, 0) for f in feats]

    base = dict(learning_rate=0.05, subsample=0.8, subsample_freq=1, random_state=42, n_jobs=-1, verbose=-1,
                monotone_constraints=monotone, monotone_constraints_method="intermediate")
    best_params = {"num_leaves": 127, "max_depth": 10, "min_child_samples": 50, "colsample_bytree": 0.8, "reg_lambda": 1.0}
    search = []
    if args.trials:
        # Recherche aléatoire sur un sous-échantillon, apprentissage rapide (lr 0,1, 400 arbres)
        idx_fit = np.flatnonzero(fit)
        sub = rng.choice(idx_fit, size=min(400_000, len(idx_fit)), replace=False)
        best_auc = -1.0
        for t in range(args.trials):
            params = {k: v[rng.integers(len(v))] for k, v in SEARCH_SPACE.items()}
            m = LGBMClassifier(n_estimators=400, **{**base, "learning_rate": 0.1}, **params)
            m.fit(X_all.iloc[sub], y_all[sub])
            auc = roc_auc_score(y_all[valid], m.predict_proba(X_all[valid])[:, 1])
            search.append({**{k: (v.item() if hasattr(v, "item") else v) for k, v in params.items()}, "valid_auc": round(float(auc), 4)})
            print(f"  essai {t + 1}/{args.trials} : AUC {auc:.4f} {params}")
            if auc > best_auc:
                best_auc, best_params = auc, {k: (v.item() if hasattr(v, "item") else v) for k, v in params.items()}
            del m
            gc.collect()

    model = LGBMClassifier(n_estimators=args.trees, **base, **best_params)
    model.fit(X_all[fit], y_all[fit], eval_set=[(X_all[valid], y_all[valid])], eval_metric="auc",
              callbacks=[early_stopping(100), log_evaluation(250)])

    # Recalibration de Platt sur le logit brut
    raw_cal = model.predict(X_all[calib], raw_score=True)
    lr = LogisticRegression(C=1e6).fit(raw_cal.reshape(-1, 1), y_all[calib])
    final = CalibratedClassifier(model, lr.coef_[0][0], lr.intercept_[0])

    p_cal = final.predict_proba(X_all[calib])[:, 1]
    thresholds = {m: round(threshold_for_recall(y_all[calib], p_cal, r), 4) for m, r in RECALL_TARGETS.items()}
    levels = {
        "warning": round(threshold_for_recall(y_all[calib], p_cal, RECALL_MODERATE), 4),
        "serious": thresholds["standard"],
        "critical": thresholds["strict"],
    }

    p_test = final.predict_proba(X_all[test])[:, 1]
    old_feats = list(old["feature_names"])
    X_old = engineer(df[test], old_feats)
    if "Distance(mi)" in old_feats:  # v2 : distance fixée comme à l'inférence
        X_old["Distance(mi)"] = 0.0
    old_test = old["model"].predict_proba(X_old)[:, 1]
    test_years = sorted(set(years[test].tolist()))

    version = "4.0"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "version": version,
        "data": {"rows": int(len(df)), "shards": len(paths), "per_shard": args.per_shard, "fit": int(fit.sum()),
                 "valid": int(valid.sum()), "calibration": int(calib.sum()), "test": int(test.sum()),
                 "test_year": test_years[0] if len(test_years) == 1 else f"{test_years[0]}-{test_years[-1]}",
                 "train_years": sorted(set(years[~test].tolist()))},
        "best_iteration": int(model.best_iteration_ or args.trees),
        "hyperparameters": best_params,
        "search": search,
        "monotone_constraints": MONOTONE,
        "features": len(feats),
        "removed_features": ["Distance(mi)"],
        "added_features": ROAD_CLASS_FEATURES,
        "calibration_params": {"a": final.a, "b": final.b},
        "thresholds": thresholds,
        "levels": levels,
        "test_metrics": metrics(y_all[test], p_test),
        "test_calibration": calibration(y_all[test], p_test),
        "previous_model_on_same_test": {
            **metrics(y_all[test], old_test),
            "version": str(old.get("version", "2.0")),
            "note": "Modèle précédent évalué sur les mêmes accidents de test.",
        },
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))

    backup = MODEL_PATH.with_name(f"saferoad_model_v{str(old.get('version', '2')).split('.')[0]}.pkl")
    if not backup.exists():
        shutil.copy2(MODEL_PATH, backup)
    joblib.dump({
        "model": final,
        "feature_names": feats,
        "threshold_standard": thresholds["standard"],
        "threshold_pro": thresholds["pro"],
        "threshold_strict": thresholds["strict"],
        "levels": levels,
        "roc_auc": report["test_metrics"]["roc_auc"],
        "version": version,
        "calibrated": True,
        "trained_at": report["generated_at"],
    }, MODEL_PATH)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Modèle enregistré : {MODEL_PATH} (précédent : {backup.name})")


if __name__ == "__main__":
    main()
