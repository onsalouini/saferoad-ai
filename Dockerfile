# Image unique SafeRoad AI (déploiement) : l'API FastAPI sert aussi le site React construit.
# Même origine pour le site et l'API -> cookie de session first-party, pas de CORS.
#   docker build -t saferoad . && docker run -p 8000:8000 --env-file api/.env saferoad

# 1. Frontend
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Chaîne vide = appels relatifs vers la même origine
ENV VITE_API_URL=""
RUN npm run build

# 2. API
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/
COPY ml/reports/ ml/reports/
COPY ml/evaluate.py ml/train.py ml/
COPY --from=web /web/dist frontend/dist
# Le modèle (non versionné) est téléchargé au démarrage depuis MODEL_URL s'il est absent

WORKDIR /app/api
ENV PYTHONUNBUFFERED=1 PORT=8000
EXPOSE 8000
# Un seul worker : le planificateur d'alertes tourne dans le processus de l'API
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
