# Image de l'API SafeRoad AI. Contexte de build : racine du dépôt (voir docker-compose.yml).
FROM python:3.12-slim

# libgomp1 : requis par LightGBM
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY ml/reports/ ml/reports/
COPY ml/evaluate.py ml/train.py ml/
# Le modèle (ml/models/saferoad_model.pkl, non versionné) est monté en volume

WORKDIR /app/api
ENV PYTHONUNBUFFERED=1
EXPOSE 8000
# Un seul worker : le planificateur d'alertes tourne dans le processus de l'API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
