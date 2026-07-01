# api/models.py
import joblib
import pandas as pd
import numpy as np
import os
from pydantic import BaseModel, Field
from typing import Optional

# ==================== MODÈLE PYDANTIC ====================
class PredictionRequest(BaseModel):
    # Localisation
    Start_Lat: float
    Start_Lng: float
    State: str
    City: Optional[str] = "Unknown"
    
    # Météo - Utiliser les noms exacts du modèle
    Temperature_F: float = Field(..., alias="Temperature_F")
    Humidity: Optional[float] = 50.0
    Pressure: Optional[float] = 29.9
    Visibility_mi: float = Field(..., alias="Visibility_mi")
    Precipitation_in: float = Field(..., alias="Precipitation_in")
    Wind_Speed_mph: float = Field(..., alias="Wind_Speed_mph")
    Weather_Condition: str
    
    # Temps
    Hour: int
    Month: int
    DayOfWeek: int
    IsWeekend: int
    IsRushHour: int
    
    # POI
    Junction: int
    Traffic_Signal: int
    Crossing: int
    Bump: int
    
    # Mode
    mode: str = "standard"
    
    class Config:
        populate_by_name = True
        extra = "allow"  # Permet d'accepter des champs supplémentaires

# ==================== CHARGEMENT DU MODÈLE ====================
MODEL_PATH = os.path.join(os.path.dirname(__file__), "../ml/models/saferoad_model.pkl")

try:
    model_data = joblib.load(MODEL_PATH)
    model = model_data["model"]
    feature_names = model_data["feature_names"]
    print(f"✅ Modèle chargé : {len(feature_names)} colonnes")
except Exception as e:
    print(f"❌ Erreur de chargement du modèle : {e}")
    model = None
    feature_names = []

THRESHOLDS = {
    "standard": model_data.get("threshold_standard", 0.65) if model_data else 0.65,
    "pro": model_data.get("threshold_pro", 0.75) if model_data else 0.75,
    "strict": model_data.get("threshold_strict", 0.85) if model_data else 0.85
}

# ==================== FONCTIONS ====================
def get_season(month: int) -> str:
    if month in [12, 1, 2]: return "Winter"
    elif month in [3, 4, 5]: return "Spring"
    elif month in [6, 7, 8]: return "Summer"
    else: return "Fall"

def prepare_features(data: dict) -> pd.DataFrame:
    """
    Prépare les 94 features exactes du modèle
    """
    # ✅ Utiliser les noms exacts du modèle avec fallback
    temp = data.get("Temperature_F", data.get("Temperature", 55))
    humidity = data.get("Humidity", data.get("Humidity(%)", 50))
    pressure = data.get("Pressure", data.get("Pressure(in)", 29.9))
    visibility = data.get("Visibility_mi", data.get("Visibility", 10))
    precip = data.get("Precipitation_in", data.get("Precipitation", 0))
    wind = data.get("Wind_Speed_mph", data.get("Wind_Speed", 5))
    state = data.get("State", "OH")
    weather = data.get("Weather_Condition", "Clear")
    month = data.get("Month", 6)
    
    row = {
        # Localisation
        "Start_Lat": float(data.get("Start_Lat", 39.865147)),
        "Start_Lng": float(data.get("Start_Lng", -84.058723)),
        
        # Météo (TOUS les champs)
        "Temperature(F)": float(temp),
        "Humidity(%)": float(humidity),
        "Pressure(in)": float(pressure),
        "Visibility(mi)": float(visibility),
        "Precipitation(in)": float(precip),
        "Wind_Speed(mph)": float(wind),
        "Weather_Condition": weather,
        
        # Temps
        "Hour": int(data.get("Hour", 12)),
        "DayOfWeek": int(data.get("DayOfWeek", 3)),
        "Month": int(month),
        "IsWeekend": int(data.get("IsWeekend", 0)),
        "IsRushHour": int(data.get("IsRushHour", 0)),
        
        # POI
        "Junction": int(data.get("Junction", 0)),
        "Traffic_Signal": int(data.get("Traffic_Signal", 0)),
        "Crossing": int(data.get("Crossing", 0)),
        "Bump": int(data.get("Bump", 0)),
        "Stop": int(data.get("Stop", 0)),
        "Roundabout": int(data.get("Roundabout", 0)),
        "Give_Way": int(data.get("Give_Way", 0)),
        "Railway": int(data.get("Railway", 0)),
        "Amenity": int(data.get("Amenity", 0)),
        "No_Exit": int(data.get("No_Exit", 0)),
        "Traffic_Calming": int(data.get("Traffic_Calming", 0)),
        "Station": int(data.get("Station", 0)),
        "Turning_Loop": int(data.get("Turning_Loop", 0)),
        "Distance(mi)": float(data.get("Distance(mi)", 0)),
    }

    # One-hot Weather_Condition
    top_weather = [
        "Fair", "Clear", "Mostly Cloudy", "Partly Cloudy", "Overcast",
        "Light Rain", "Rain", "Light Snow", "Snow", "Fog",
        "Heavy Rain", "Thunderstorm", "Haze", "Drizzle", "Cloudy"
    ]
    
    if weather not in top_weather:
        weather = "Other"
    
    for w in top_weather[1:]:  # drop_first=True
        row[f"Weather_Condition_{w}"] = 1 if weather == w else 0
    row["Weather_Condition_Other"] = 1 if weather == "Other" else 0

    # One-hot Season
    season = get_season(month)
    for s in ["Spring", "Summer", "Winter"]:  # drop_first=True (Fall droppé)
        row[f"Season_{s}"] = 1 if season == s else 0

    # One-hot State
    states = [
        "AL","AR","AZ","CA","CO","CT","DC","DE","FL","GA",
        "IA","ID","IL","IN","KS","KY","LA","MA","MD","ME",
        "MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ",
        "NM","NV","NY","OH","OK","OR","PA","RI","SC","SD",
        "TN","TX","UT","VA","VT","WA","WI","WV","WY"
    ]
    
    for s in states[1:]:  # drop_first=True (AL droppé)
        row[f"State_{s}"] = 1 if state == s else 0

    # Créer le DataFrame
    df = pd.DataFrame([row])

    # Ajouter les colonnes manquantes avec 0
    for col in feature_names:
        if col not in df.columns:
            df[col] = 0

    # Garder l'ordre exact du modèle
    df = df[feature_names]

    return df

def predict(data: dict, mode: str = "standard") -> dict:
    """
    Prédit le risque d'accident
    """
    try:
        # Vérifier que le modèle est chargé
        if model is None:
            return {
                "risk_score": 0,
                "risk_level": "Erreur",
                "threshold_used": 0,
                "is_high_risk": False,
                "explanation": "Modèle non chargé",
                "probability": 0.0
            }
        
        # Récupérer le seuil
        threshold = THRESHOLDS.get(mode, THRESHOLDS["standard"])
        
        # Préparer les features
        df = prepare_features(data)
        
        # Prédire
        proba = model.predict_proba(df)[0][1]
        is_high_risk = bool(proba >= threshold)
        risk_score = round(proba * 100, 1)
        
        # Niveau de risque
        if proba < 0.40:
            risk_level = "Faible"
            explanation = "✅ Conditions favorables. Trajet sans risque particulier."
        elif proba < 0.65:
            risk_level = "Modéré"
            explanation = "⚠️ Quelques facteurs de risque détectés. Prudence recommandée."
        elif proba < 0.80:
            risk_level = "Élevé"
            explanation = "🔴 Conditions dangereuses détectées. Envisagez un autre horaire."
        else:
            risk_level = "Très élevé"
            explanation = "🚨 Risque très élevé. Fortement déconseillé de partir maintenant."

        return {
            "risk_score": risk_score,
            "risk_level": risk_level,
            "threshold_used": threshold,
            "is_high_risk": is_high_risk,
            "explanation": explanation,
            "probability": float(proba)
        }
        
    except Exception as e:
        print(f"❌ Erreur dans predict : {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "risk_score": 0,
            "risk_level": "Erreur",
            "threshold_used": 0,
            "is_high_risk": False,
            "explanation": f"Erreur: {str(e)}",
            "probability": 0.0
        }