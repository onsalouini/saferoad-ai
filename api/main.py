# api/main.py
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Database
from ml.features import WEATHER_CHOICES
from ml.predict import model_service
from routes import auth, geo, history, predict


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    yield
    await Database.disconnect()


app = FastAPI(
    title="SafeRoad AI API",
    description="Prédiction du risque de gravité d'accident sur un trajet (LightGBM, US Accidents).",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)
app.include_router(geo.router)
app.include_router(auth.router)
app.include_router(history.router)


@app.get("/", tags=["Système"])
def root():
    return {"message": "SafeRoad AI API is running", "docs": "/docs"}


@app.get("/health", tags=["Système"])
def health():
    return {"status": "ok" if model_service.ready else "degraded",
            "model_loaded": model_service.ready, "database": Database.backend}


@app.get("/model/info", tags=["Modèle"])
def model_info():
    """Métadonnées, importance des variables et rapport d'évaluation du modèle."""
    return model_service.info()


@app.get("/model/options", tags=["Modèle"])
def model_options():
    return {"weather_conditions": WEATHER_CHOICES, "modes": model_service.thresholds}
