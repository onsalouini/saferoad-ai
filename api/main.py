# api/main.py
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Database
from ml.features import WEATHER_CHOICES
from ml.predict import model_service
from routes import account, assistant as assistant_routes, auth, geo, history, predict, reports, trips
from services import assistant, incidents, mailer, push, scheduler, shared

# Suivi des erreurs (optionnel) : SENTRY_DSN dans .env
if os.getenv("SENTRY_DSN"):
    import sentry_sdk

    sentry_sdk.init(dsn=os.getenv("SENTRY_DSN"), traces_sample_rate=float(os.getenv("SENTRY_TRACES", "0.1")),
                    environment=os.getenv("ENVIRONMENT", "development"), send_default_pii=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    task = asyncio.create_task(scheduler.run_forever()) if scheduler.ENABLED else None
    yield
    if task:
        task.cancel()
    await Database.disconnect()


app = FastAPI(
    title="SafeRoad AI API",
    description="Prédiction du risque de gravité d'accident sur un trajet (LightGBM, US Accidents).",
    version="4.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(","),
    allow_credentials=True,  # cookie de session httpOnly
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)
app.include_router(geo.router)
app.include_router(auth.router)
app.include_router(history.router)
app.include_router(assistant_routes.router)
app.include_router(trips.router)
app.include_router(reports.router)
app.include_router(account.router)


@app.get("/", tags=["Système"])
def root():
    return {"message": "SafeRoad AI API is running", "docs": "/docs"}


@app.get("/health", tags=["Système"])
def health():
    return {"status": "ok" if model_service.ready else "degraded",
            "model_loaded": model_service.ready, "database": Database.backend,
            "assistant": assistant.available(), "email": mailer.configured(),
            "scheduler": scheduler.ENABLED, "model_version": model_service.version,
            "push": push.public_key() is not None, "traffic": incidents.available(),
            "redis": shared.REDIS_URL is not None, "sentry": bool(os.getenv("SENTRY_DSN"))}


@app.get("/model/info", tags=["Modèle"])
def model_info():
    """Métadonnées, importance des variables et rapport d'évaluation du modèle."""
    return model_service.info()


@app.get("/model/options", tags=["Modèle"])
def model_options():
    return {"weather_conditions": WEATHER_CHOICES, "modes": model_service.thresholds, "levels": model_service.level_bounds}
