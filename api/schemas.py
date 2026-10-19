# api/schemas.py
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

Mode = Literal["standard", "pro", "strict"]


class RoadFeatures(BaseModel):
    Junction: bool = False
    Traffic_Signal: bool = False
    Crossing: bool = False
    Stop: bool = False
    Roundabout: bool = False
    Give_Way: bool = False
    Railway: bool = False
    Bump: bool = False
    Amenity: bool = False
    Station: bool = False


class SituationInput(RoadFeatures):
    """Simulation manuelle : toutes les conditions sont fournies par l'utilisateur."""
    Start_Lat: float = Field(..., ge=-90, le=90)
    Start_Lng: float = Field(..., ge=-180, le=180)
    State: Optional[str] = Field(None, description="Code US à 2 lettres ; détecté depuis les coordonnées si absent")
    City: Optional[str] = None

    Temperature_F: float = Field(..., ge=-60, le=140)
    Humidity: float = Field(..., ge=0, le=100)
    Pressure: float = Field(..., ge=20, le=35)
    Visibility_mi: float = Field(..., ge=0, le=100)
    Wind_Speed_mph: float = Field(..., ge=0, le=250)
    Precipitation_in: float = Field(..., ge=0, le=25)
    Weather_Condition: str

    Hour: int = Field(..., ge=0, le=23)
    Month: int = Field(..., ge=1, le=12)
    DayOfWeek: int = Field(..., ge=0, le=6, description="0 = lundi … 6 = dimanche")
    IsNight: Optional[bool] = None

    mode: Mode = "standard"


class Place(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    label: Optional[str] = None


class TripInput(BaseModel):
    origin: Place
    destination: Place
    mode: Mode = "standard"
    road: RoadFeatures = RoadFeatures()


class RegisterInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginInput(BaseModel):
    email: EmailStr
    password: str
