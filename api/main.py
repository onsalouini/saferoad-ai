from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from schemas import TripInput, RiskOutput
from models import predict

app = FastAPI(
    title="SafeRoad AI API",
    description="Road Risk Prediction API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/")
def root():
    return {"message": "SafeRoad AI API is running"}

@app.post("/predict", response_model=RiskOutput)
def predict_risk(trip: TripInput):
    result = predict(trip.dict(), trip.mode)
    return result

@app.get("/health")
def health():
    return {"status": "ok"}