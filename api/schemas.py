from pydantic import BaseModel
from typing import Literal

class TripInput(BaseModel):
    # Localisation
    Start_Lat: float
    Start_Lng: float
    State: str

    # Météo
    Temperature_F: float
    Humidity: float
    Pressure: float
    Visibility_mi: float
    Wind_Speed_mph: float
    Precipitation_in: float
    Weather_Condition: str

    # Temporel
    Hour: int
    Month: int
    DayOfWeek: int

    # Route
    Junction: bool = False
    Traffic_Signal: bool = False
    Crossing: bool = False

    # Mode de prédiction
    mode: Literal["standard", "pro", "strict"] = "standard"

class RiskOutput(BaseModel):
    risk_score: float
    risk_level: str
    threshold_used: float
    is_high_risk: bool
    explanation: str