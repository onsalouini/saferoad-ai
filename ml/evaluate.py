"""
Évaluation de la fiabilité du modèle SafeRoad AI.

Usage :
    python ml/evaluate.py --data data/raw/shard0.parquet [--sample 300000]

Produit :
    ml/reports/evaluation.json   (consommé par l'API -> page « Modèle »)
    ml/reports/EVALUATION.md     (rapport lisible)

Données : US Accidents (Moosavi et al., mars 2023). Le dataset ne contient QUE
des accidents ; la cible du modèle est donc la gravité d'un accident, pas
l'occurrence d'un accident (voir section « Cible » du rapport).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))
from ml.features import (  # noqa: E402
    MODEL_WEATHER,
    ROAD_FEATURES,
    RUSH_HOURS,
    STATES,
    build_row,
    season_of,
    to_frame,
)

REPORT_DIR = ROOT / "ml" / "reports"
RNG = np.random.default_rng(42)


# --------------------------------------------------------------------------- data
def load(path: str, sample: int) -> pd.DataFrame:
    cols = [
        "Severity", "Start_Time", "Start_Lat", "Start_Lng", "Distance(mi)", "State",
        "Temperature(F)", "Humidity(%)", "Pressure(in)", "Visibility(mi)",
        "Wind_Speed(mph)", "Precipitation(in)", "Weather_Condition", "Sunrise_Sunset",
        *ROAD_FEATURES,
    ]
    df = pd.read_parquet(path, columns=cols)
    if sample and len(df) > sample:
        df = df.sample(sample, random_state=42)
    t = pd.to_datetime(df["Start_Time"], format="mixed", errors="coerce")
    df = df.assign(
        Hour=t.dt.hour, DayOfWeek=t.dt.dayofweek, Month=t.dt.month, Year=t.dt.year
    ).dropna(subset=["Hour", "Sunrise_Sunset"])
    return df.reset_index(drop=True)


def engineer(df: pd.DataFrame, feature_names: list[str], night_is_one: bool = True) -> pd.DataFrame:
    """Reproduit le prétraitement du notebook (top-15 météo -> sinon Other, one-hot drop_first)."""
    X = pd.DataFrame(index=df.index)
    for c in ["Start_Lat", "Start_Lng", "Temperature(F)", "Humidity(%)", "Pressure(in)",
              "Visibility(mi)", "Wind_Speed(mph)", "Precipitation(in)", "Distance(mi)"]:
        X[c] = df[c].astype(float)
    for c in ROAD_FEATURES:
        X[c] = df[c].astype(int)
    night = (df["Sunrise_Sunset"] == "Night").astype(int)
    X["Sunrise_Sunset"] = night if night_is_one else 1 - night
    X["Hour"] = df["Hour"].astype(int)
    X["DayOfWeek"] = df["DayOfWeek"].astype(int)
    X["Month"] = df["Month"].astype(int)
    X["IsWeekend"] = (X["DayOfWeek"] >= 5).astype(int)
    X["IsRushHour"] = X["Hour"].isin(RUSH_HOURS).astype(int)
    known = set(MODEL_WEATHER) | {"Clear"}
    w = df["Weather_Condition"].where(df["Weather_Condition"].isin(known), "Other")
    for c in MODEL_WEATHER:
        X[f"Weather_Condition_{c}"] = (w == c).astype(int)
    season = X["Month"].map(season_of)
    for s in ("Spring", "Summer", "Winter"):
        X[f"Season_{s}"] = (season == s).astype(int)
    for s in STATES[1:]:
        X[f"State_{s}"] = (df["State"] == s).astype(int)
    return X[feature_names]


# ----------------------------------------------------------------------- metrics
def threshold_table(y, p, thresholds: dict) -> list[dict]:
    rows = []
    for name, t in [("0.50", 0.5)] + [(k, v) for k, v in thresholds.items()]:
        pred = (p >= t).astype(int)
        rows.append({
            "mode": name, "threshold": t,
            "flagged_rate": round(float(pred.mean()), 4),
            "precision": round(float(precision_score(y, pred, zero_division=0)), 4),
            "recall": round(float(recall_score(y, pred, zero_division=0)), 4),
            "f1": round(float(f1_score(y, pred, zero_division=0)), 4),
            "tp": int(((pred == 1) & (y == 1)).sum()), "fp": int(((pred == 1) & (y == 0)).sum()),
            "fn": int(((pred == 0) & (y == 1)).sum()), "tn": int(((pred == 0) & (y == 0)).sum()),
        })
    return rows


def calibration(y, p, bins: int = 10) -> list[dict]:
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges) - 1, 0, bins - 1)
    out = []
    for b in range(bins):
        m = idx == b
        if m.sum() == 0:
            continue
        out.append({
            "bin": f"{edges[b]:.1f}-{edges[b + 1]:.1f}",
            "predicted": round(float(p[m].mean()), 4),
            "observed": round(float(y[m].mean()), 4),
            "count": int(m.sum()),
        })
    return out


def permutation_drop(model, X: pd.DataFrame, y, base_auc: float, groups: dict) -> list[dict]:
    out = []
    for label, cols in groups.items():
        Xp = X.copy()
        perm = RNG.permutation(len(Xp))
        Xp[cols] = Xp[cols].to_numpy()[perm]  # permute le groupe entier, conjointement
        auc = roc_auc_score(y, model.predict_proba(Xp)[:, 1])
        out.append({"group": label, "auc_drop": round(base_auc - auc, 4)})
    return sorted(out, key=lambda r: r["auc_drop"], reverse=True)


def directional_tests(model, feature_names, df: pd.DataFrame, n: int = 300) -> list[dict]:
    """Change UN facteur à la fois sur n situations réelles, via build_row (chemin de l'API)."""
    base_rows = df.sample(n, random_state=7)
    scenarios = []
    for _, r in base_rows.iterrows():
        scenarios.append({
            "Start_Lat": r["Start_Lat"], "Start_Lng": r["Start_Lng"], "State": r["State"],
            "Temperature_F": 60, "Humidity": 60, "Pressure": 29.9, "Visibility_mi": 10,
            "Wind_Speed_mph": 7, "Precipitation_in": 0, "Weather_Condition": "Fair",
            "Hour": 13, "DayOfWeek": 2, "Month": 5, "IsNight": False,
        })
    tests = [
        ("Pluie forte (vs beau temps)", {"Weather_Condition": "Heavy Rain", "Precipitation_in": 0.3, "Visibility_mi": 3}, "hausse"),
        ("Neige légère (vs beau temps)", {"Weather_Condition": "Light Snow", "Temperature_F": 28, "Visibility_mi": 2}, "hausse"),
        ("Brouillard, visibilité 0,5 mi", {"Weather_Condition": "Fog", "Visibility_mi": 0.5}, "hausse"),
        ("Nuit (23 h)", {"Hour": 23, "IsNight": True}, "hausse"),
        ("Heure de pointe (17 h)", {"Hour": 17}, "hausse"),
        ("Vent fort (35 mph)", {"Wind_Speed_mph": 35, "Weather_Condition": "Fair / Windy"}, "hausse"),
        ("Feu de signalisation", {"Traffic_Signal": 1}, "?"),
        ("Intersection", {"Junction": 1}, "?"),
    ]
    p0 = model.predict_proba(to_frame([build_row(s) for s in scenarios], feature_names))[:, 1]
    out = []
    for label, change, expected in tests:
        p1 = model.predict_proba(
            to_frame([build_row({**s, **change}) for s in scenarios], feature_names))[:, 1]
        d = p1 - p0
        out.append({
            "test": label, "expected": expected,
            "mean_delta_pts": round(float(d.mean()) * 100, 2),
            "share_increase": round(float((d > 0).mean()), 3),
            # cohérent = hausse en moyenne ET dans la majorité des cas
            "consistent": None if expected == "?" else bool(d.mean() > 0 and (d > 0).mean() >= 0.5),
        })
    return out


def location_spread(model, feature_names, df: pd.DataFrame, n: int = 500) -> dict:
    """Mêmes conditions partout : quelle part de la variance vient du seul lieu ?"""
    rows = df.sample(n, random_state=11)
    scen = [build_row({
        "Start_Lat": r["Start_Lat"], "Start_Lng": r["Start_Lng"], "State": r["State"],
        "Weather_Condition": "Fair", "Hour": 13, "DayOfWeek": 2, "Month": 5, "IsNight": False,
    }) for _, r in rows.iterrows()]
    p = model.predict_proba(to_frame(scen, feature_names))[:, 1]
    return {
        "n": n, "min": round(float(p.min()), 4), "p10": round(float(np.quantile(p, .1)), 4),
        "median": round(float(np.median(p)), 4), "p90": round(float(np.quantile(p, .9)), 4),
        "max": round(float(p.max()), 4),
    }


# -------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(ROOT / "data" / "raw" / "shard0.parquet"))
    ap.add_argument("--sample", type=int, default=300_000)
    ap.add_argument("--model", default=str(ROOT / "ml" / "models" / "saferoad_model.pkl"))
    args = ap.parse_args()

    bundle = joblib.load(args.model)
    model, feats = bundle["model"], list(bundle["feature_names"])
    thresholds = {k.replace("threshold_", ""): float(v) for k, v in bundle.items() if k.startswith("threshold_")}

    df = load(args.data, args.sample)
    print(f"{len(df):,} accidents évalués")

    # 1. Identification de la cible et de l'encodage jour/nuit (par AUC)
    hypotheses = []
    for night_is_one in (True, False):
        X = engineer(df, feats, night_is_one)
        p = model.predict_proba(X)[:, 1]
        for name, y in [("Severity >= 3", df["Severity"] >= 3), ("Severity == 4", df["Severity"] == 4),
                        ("Severity >= 2", df["Severity"] >= 2)]:
            hypotheses.append({"target": name, "night_encoding": "Night=1" if night_is_one else "Night=0",
                               "roc_auc": round(roc_auc_score(y.astype(int), p), 4)})
    best = max(hypotheses, key=lambda h: h["roc_auc"])
    print("Hypothèse retenue :", best)
    night_is_one = best["night_encoding"] == "Night=1"
    target = {"Severity >= 3": df["Severity"] >= 3, "Severity == 4": df["Severity"] == 4,
              "Severity >= 2": df["Severity"] >= 2}[best["target"]].astype(int).to_numpy()

    X = engineer(df, feats, night_is_one)
    p = model.predict_proba(X)[:, 1]
    auc = roc_auc_score(target, p)

    # 2. Fuite de données : Distance(mi) réelle vs valeur fixe utilisée par l'API
    median_dist = float(df["Distance(mi)"].median())
    X_fixed = X.copy()
    X_fixed["Distance(mi)"] = median_dist
    p_fixed = model.predict_proba(X_fixed)[:, 1]
    auc_fixed = roc_auc_score(target, p_fixed)

    # 3. Importance par permutation (sur 100k lignes)
    sub = RNG.choice(len(X), size=min(100_000, len(X)), replace=False)
    Xs, ys = X.iloc[sub].reset_index(drop=True), target[sub]
    base_sub = roc_auc_score(ys, model.predict_proba(Xs)[:, 1])
    groups = {
        "Localisation (lat/lng)": ["Start_Lat", "Start_Lng"],
        "Distance d'impact": ["Distance(mi)"],
        "État": [c for c in feats if c.startswith("State_")],
        "Météo (conditions + mesures)": [c for c in feats if c.startswith("Weather_Condition_")]
        + ["Temperature(F)", "Humidity(%)", "Pressure(in)", "Visibility(mi)", "Wind_Speed(mph)", "Precipitation(in)"],
        "Temps (heure, jour, mois, saison)": ["Hour", "DayOfWeek", "Month", "IsWeekend", "IsRushHour",
                                             "Sunrise_Sunset", "Season_Spring", "Season_Summer", "Season_Winter"],
        "Infrastructure routière": list(ROAD_FEATURES),
    }
    perm = permutation_drop(model, Xs, ys, base_sub, groups)

    # 4. Stabilité par année et par État
    by_year = []
    for yv, g in df.groupby("Year"):
        m = (df["Year"] == yv).to_numpy()
        if target[m].min() != target[m].max():
            by_year.append({"year": int(yv), "n": int(m.sum()), "positive_rate": round(float(target[m].mean()), 4),
                            "roc_auc": round(roc_auc_score(target[m], p[m]), 4),
                            "roc_auc_distance_fixed": round(roc_auc_score(target[m], p_fixed[m]), 4)})
    by_state = []
    for st in df["State"].value_counts().head(12).index:
        m = (df["State"] == st).to_numpy()
        if target[m].min() != target[m].max():
            by_state.append({"state": st, "n": int(m.sum()), "positive_rate": round(float(target[m].mean()), 4),
                             "roc_auc": round(roc_auc_score(target[m], p_fixed[m]), 4)})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dataset": {
            "source": "US Accidents (Moosavi et al., mars 2023) — miroir Hugging Face yuvidhepe/us-accidents-updated, fragment 1/7",
            "rows_evaluated": int(len(df)),
            "years": sorted(int(y) for y in df["Year"].unique()),
            "positive_rate": round(float(target.mean()), 4),
            "distance_median_mi": median_dist,
        },
        "target": {
            "identified": best["target"],
            "night_encoding": best["night_encoding"],
            "hypotheses": hypotheses,
            "meaning": "Probabilité qu'un accident survenant dans ces conditions soit grave (Severity 3-4). "
                       "Le dataset ne contient que des accidents : le modèle ne prédit pas la probabilité qu'un accident se produise.",
        },
        "metrics": {
            "declared_roc_auc": bundle.get("roc_auc"),
            "roc_auc": round(auc, 4),
            "pr_auc": round(average_precision_score(target, p), 4),
            "brier": round(brier_score_loss(target, p), 4),
            "roc_auc_distance_fixed": round(auc_fixed, 4),
            "pr_auc_distance_fixed": round(average_precision_score(target, p_fixed), 4),
            "brier_distance_fixed": round(brier_score_loss(target, p_fixed), 4),
        },
        "thresholds": threshold_table(target, p_fixed, thresholds),
        "calibration": calibration(target, p_fixed),
        "permutation_importance": perm,
        "by_year": by_year,
        "by_state": by_state,
        "directional_tests": directional_tests(model, feats, df),
        "location_only_spread": location_spread(model, feats, df),
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "evaluation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
