# api/ml/features.py
"""
Construction des variables d'entrée du modèle.

Ce module est la SEULE source de vérité pour transformer une situation
(lieu, météo, heure, route) en vecteur de 94 colonnes attendu par le modèle.
Il est partagé par l'API et par le script d'évaluation (ml/evaluate.py),
ce qui garantit que l'on évalue exactement ce que l'API envoie au modèle.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Catégories météo présentes dans le modèle (one-hot, "Clear" = référence supprimée)
MODEL_WEATHER = [
    "Cloudy", "Fair", "Fair / Windy", "Fog", "Haze", "Heavy Rain",
    "Light Drizzle", "Light Rain", "Light Snow", "Mostly Cloudy", "Other",
    "Overcast", "Partly Cloudy", "Rain", "Scattered Clouds",
]
WEATHER_BASELINE = "Clear"
WEATHER_CHOICES = [WEATHER_BASELINE] + MODEL_WEATHER

# États présents dans le modèle (one-hot, "AL" = référence supprimée)
STATES = [
    "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME",
    "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ",
    "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD",
    "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY",
]

ROAD_FEATURES = [
    "Junction", "Traffic_Signal", "Crossing", "Stop", "Roundabout", "Give_Way",
    "Railway", "Amenity", "Bump", "No_Exit", "Traffic_Calming", "Station",
    "Turning_Loop",
]

RUSH_HOURS = {7, 8, 9, 16, 17, 18, 19}

# Valeur utilisée pour Distance(mi) à l'inférence.
# Distance(mi) = longueur de route impactée PAR l'accident : elle n'est pas
# connue avant le trajet (fuite de données). On utilise la médiane du dataset
# (0 mi) ; l'évaluation montre que l'AUC est même meilleure avec cette valeur
# fixe (0.891) qu'avec la distance réelle (0.880).
DEFAULT_DISTANCE_MI = 0.0

# Libellés lisibles pour les explications
GROUP_LABELS = {
    "location": "Localisation (lat/lng)",
    "state": "État",
    "weather": "Conditions météo",
    "season": "Saison",
    "Temperature(F)": "Température",
    "Humidity(%)": "Humidité",
    "Pressure(in)": "Pression atmosphérique",
    "Visibility(mi)": "Visibilité",
    "Wind_Speed(mph)": "Vent",
    "Precipitation(in)": "Précipitations",
    "Hour": "Heure de la journée",
    "DayOfWeek": "Jour de la semaine",
    "Month": "Mois",
    "IsWeekend": "Week-end",
    "IsRushHour": "Heure de pointe",
    "Sunrise_Sunset": "Jour / nuit",
    "Distance(mi)": "Distance d'impact (fixe)",
    "Junction": "Intersection",
    "Traffic_Signal": "Feu de signalisation",
    "Crossing": "Passage piéton",
    "Stop": "Panneau stop",
    "Roundabout": "Rond-point",
    "Give_Way": "Cédez-le-passage",
    "Railway": "Passage à niveau",
    "Amenity": "Commerces / services",
    "Bump": "Ralentisseur",
    "No_Exit": "Voie sans issue",
    "Traffic_Calming": "Zone apaisée",
    "Station": "Station",
    "Turning_Loop": "Boucle de demi-tour",
}


def season_of(month: int) -> str:
    if month in (12, 1, 2):
        return "Winter"
    if month in (3, 4, 5):
        return "Spring"
    if month in (6, 7, 8):
        return "Summer"
    return "Fall"


def normalize_weather(condition: str | None) -> str:
    """Ramène une condition météo libre vers une catégorie connue du modèle."""
    if not condition:
        return WEATHER_BASELINE
    c = condition.strip()
    if c in WEATHER_CHOICES:
        return c
    low = c.lower()
    if low in ("clear",):
        return "Clear"
    if "fair" in low:
        return "Fair / Windy" if "wind" in low else "Fair"
    if "thunder" in low or "t-storm" in low:
        return "Other"
    if "heavy rain" in low:
        return "Heavy Rain"
    if "light rain" in low:
        return "Light Rain"
    if "drizzle" in low:
        return "Light Drizzle"
    if "rain" in low or "shower" in low:
        return "Rain"
    if "light snow" in low:
        return "Light Snow"
    if "fog" in low or "mist" in low:
        return "Fog"
    if "haze" in low or "smoke" in low:
        return "Haze"
    if "mostly cloudy" in low:
        return "Mostly Cloudy"
    if "partly cloudy" in low:
        return "Partly Cloudy"
    if "scattered" in low:
        return "Scattered Clouds"
    if "overcast" in low:
        return "Overcast"
    if "cloud" in low:
        return "Cloudy"
    return "Other"


def build_row(data: dict) -> dict:
    """Situation -> dictionnaire {colonne_modèle: valeur} (sans réordonner)."""
    month = int(data.get("Month", 6))
    day = int(data.get("DayOfWeek", 2))  # 0 = lundi (convention pandas)
    hour = int(data.get("Hour", 12))
    is_night = data.get("IsNight")
    if is_night is None:
        is_night = hour < 6 or hour >= 20

    row = {
        "Start_Lat": float(data.get("Start_Lat", 39.865147)),
        "Start_Lng": float(data.get("Start_Lng", -84.058723)),
        "Temperature(F)": float(data.get("Temperature_F", 60)),
        "Humidity(%)": float(data.get("Humidity", 60)),
        "Pressure(in)": float(data.get("Pressure", 29.9)),
        "Visibility(mi)": float(data.get("Visibility_mi", 10)),
        "Wind_Speed(mph)": float(data.get("Wind_Speed_mph", 7)),
        "Precipitation(in)": float(data.get("Precipitation_in", 0)),
        "Sunrise_Sunset": 1 if is_night else 0,  # LabelEncoder : Day=0, Night=1
        "Distance(mi)": float(data.get("Distance_mi", DEFAULT_DISTANCE_MI)),
        "Hour": hour,
        "DayOfWeek": day,
        "Month": month,
        "IsWeekend": int(data.get("IsWeekend", 1 if day >= 5 else 0)),
        "IsRushHour": int(data.get("IsRushHour", 1 if hour in RUSH_HOURS else 0)),
    }
    for f in ROAD_FEATURES:
        row[f] = int(bool(data.get(f, 0)))

    weather = normalize_weather(data.get("Weather_Condition"))
    for w in MODEL_WEATHER:
        row[f"Weather_Condition_{w}"] = int(weather == w)

    season = season_of(month)
    for s in ("Spring", "Summer", "Winter"):
        row[f"Season_{s}"] = int(season == s)

    state = (data.get("State") or "").upper()
    for s in STATES[1:]:
        row[f"State_{s}"] = int(state == s)
    return row


def to_frame(rows: list[dict], feature_names: list[str]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        raise ValueError(f"Colonnes manquantes pour le modèle : {missing}")
    return df[feature_names].astype(float)


def feature_group(col: str) -> str:
    if col in ("Start_Lat", "Start_Lng"):
        return "location"
    if col.startswith("State_"):
        return "state"
    if col.startswith("Weather_Condition_"):
        return "weather"
    if col.startswith("Season_"):
        return "season"
    return col


def group_contributions(contribs: np.ndarray, feature_names: list[str]) -> dict[str, float]:
    """Agrège des contributions SHAP (log-odds) par groupe lisible."""
    out: dict[str, float] = {}
    for value, col in zip(contribs, feature_names):
        g = feature_group(col)
        out[g] = out.get(g, 0.0) + float(value)
    return out
