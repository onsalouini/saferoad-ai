# api/schemas.py
from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Mode = Literal["standard", "pro", "strict"]
Profile = Literal["standard", "moto", "poids_lourd", "jeune"]


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
    Road_Class: Literal["freeway", "highway", "local"] = "local"

    mode: Mode = "standard"
    profile: Profile = "standard"


class Place(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    label: Optional[str] = None


class TripInput(BaseModel):
    origin: Place
    destination: Place
    mode: Mode = "standard"
    profile: Profile = "standard"
    road: RoadFeatures = RoadFeatures()


class RegisterInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=60)
    email: EmailStr
    # bcrypt refuse les mots de passe de plus de 72 octets
    password: str = Field(..., min_length=8, max_length=72)
    phone: Optional[str] = Field(None, max_length=30)
    location: Optional[str] = Field(None, max_length=120)
    gender: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class LoginInput(BaseModel):
    email: EmailStr
    password: str

    # Comptes créés avec bcrypt 4 (qui tronquait en silence à 72 octets) : même troncature ici
    @field_validator("password")
    @classmethod
    def _password_bytes(cls, v: str) -> str:
        return v.encode()[:72].decode(errors="ignore")


class ForgotInput(BaseModel):
    email: EmailStr


class ResetInput(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)
    password: str = Field(..., min_length=8, max_length=72)


class SavedTripInput(BaseModel):
    origin: Place
    destination: Place
    mode: Mode = "standard"
    label: Optional[str] = Field(None, max_length=80)
    profile: Profile = "standard"
    departure_time: str = Field(..., pattern=r"^([01]\d|2[0-3]):[0-5]\d$", description="Heure habituelle de départ (HH:MM, heure locale)")
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], description="0 = lundi … 6 = dimanche")
    tz: str = Field("UTC", max_length=60, description="Fuseau IANA du navigateur, ex. Europe/Paris")
    notify_email: bool = True

    @field_validator("days")
    @classmethod
    def _days(cls, v: list[int]) -> list[int]:
        if not v or any(d not in range(7) for d in v):
            raise ValueError("Jours invalides (0 = lundi … 6 = dimanche)")
        return sorted(set(v))

    @field_validator("tz")
    @classmethod
    def _tz(cls, v: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Fuseau horaire inconnu")
        return v


class ReportInput(BaseModel):
    type: str = Field(..., max_length=30)
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    comment: Optional[str] = Field(None, max_length=200)


class ReportVote(BaseModel):
    still_there: bool


class VerifyInput(BaseModel):
    token: str = Field(..., min_length=20, max_length=200)


class PushKeys(BaseModel):
    p256dh: str = Field(..., max_length=200)
    auth: str = Field(..., max_length=100)


class PushSubscriptionInput(BaseModel):
    endpoint: str = Field(..., max_length=1000, pattern=r"^https://")
    keys: PushKeys


class DeleteAccountInput(BaseModel):
    password: str = Field(..., max_length=72)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=4000)


class ChatInput(BaseModel):
    messages: list[ChatMessage] = Field(..., min_length=1, max_length=30)
    context: Optional[dict] = Field(None, description="Résumé de l'analyse affichée (trajet ou simulation)")

    @model_validator(mode="after")
    def _check(self) -> "ChatInput":
        if self.messages[0].role != "user" or self.messages[-1].role != "user":
            raise ValueError("La conversation doit commencer et finir par un message de l'utilisateur")
        if self.context is not None and len(json.dumps(self.context, ensure_ascii=False)) > 20000:
            raise ValueError("Contexte d'analyse trop volumineux")
        return self
