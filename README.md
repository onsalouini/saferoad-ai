# SafeRoad AI

Plateforme d'IA qui estime le risque d'un trajet routier à partir de l'historique des accidents, de la météo
prévue et de l'itinéraire, puis **recommande l'itinéraire et l'heure de départ les plus sûrs**.

* **Analyse de trajet** : itinéraire réel (OSRM), météo prévue à l'heure de passage sur chaque tronçon
  (Open-Meteo), risque tronçon par tronçon sur une carte, comparaison des itinéraires et meilleur
  créneau de départ sur 24 h.
* **Simulateur** : testez un scénario (lieu, météo réelle ou saisie, heure, route) et voyez quels facteurs
  font varier le score (contributions SHAP).
* **Transparence du modèle** : performances, calibration, importance des variables, stabilité, tests de
  cohérence et limites ([rapport complet](ml/reports/EVALUATION.md)).
* **Comptes et historique** : inscription / connexion (JWT) et historique des analyses, avec relance.

> ⚠️ Le modèle a été entraîné sur des accidents **américains** (US Accidents, 7,7 M). Il estime la **gravité
> potentielle** d'un accident dans des conditions données, pas la probabilité qu'il survienne. Hors des
> États-Unis, les résultats sont indicatifs. Voir [EVALUATION.md](ml/reports/EVALUATION.md).

## Architecture

```
saferoad-ai/
├── api/                    FastAPI
│   ├── main.py             application, CORS, routes système et modèle
│   ├── ml/features.py      encodage des 94 variables (partagé avec l'évaluation)
│   ├── ml/predict.py       chargement LightGBM, prédiction, explication SHAP
│   ├── services/geo.py     Nominatim (géocodage), OSRM (itinéraires), détection de l'État US
│   ├── services/weather.py Open-Meteo (prévisions horaires -> format du modèle)
│   ├── routes/             predict, geo, auth, history
│   ├── database.py         MongoDB (MONGO_URI) ou fichier JSON local
│   └── auth.py             bcrypt + JWT
├── ml/
│   ├── models/saferoad_model.pkl   modèle (non versionné)
│   ├── evaluate.py                 évaluation de la fiabilité
│   └── reports/                    evaluation.json + EVALUATION.md
└── frontend/               React 19 + Vite + Tailwind + Leaflet
    └── src/pages/          Home, Trip, Simulator, Model, History, Auth
```

Services externes, **gratuits et sans clé** : OpenStreetMap (fond de carte), Nominatim (adresses),
OSRM (itinéraires), Open-Meteo (météo).

## Installation

Prérequis : Python 3.11+ et Node 20+.

```bash
# 1. Backend
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/macOS : source venv/bin/activate)
pip install -r requirements.txt
copy api\.env.example api\.env   # puis définir JWT_SECRET (MONGO_URI est optionnel)

# 2. Placer le modèle dans ml/models/saferoad_model.pkl

# 3. Lancer l'API
cd api
uvicorn main:app --reload --port 8000     # documentation : http://localhost:8000/docs

# 4. Frontend (autre terminal)
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

Sans `MONGO_URI`, les comptes et l'historique sont enregistrés dans `api/data/local_db.json`.

## API

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | état de l'API, du modèle et de la base |
| GET | `/model/info` | métadonnées, importance des variables, rapport d'évaluation |
| POST | `/predict` | simulation manuelle : score, niveau, facteurs explicatifs |
| POST | `/predict/trip` | analyse de trajet : itinéraires, tronçons, départs sur 24 h, recommandation |
| GET | `/geo/search?q=` | recherche d'adresse |
| GET | `/geo/reverse?lat=&lng=` | adresse et État US d'un point |
| GET | `/weather?lat=&lng=` | météo actuelle au format du modèle |
| POST | `/auth/register`, `/auth/login` | comptes (JWT) · `GET /auth/me` |
| GET / DELETE | `/history`, `/history/{id}` | historique de l'utilisateur connecté |

## Niveaux et modes

| Indice | Niveau |
|---|---|
| < 40 | Faible |
| 40–65 | Modéré |
| 65–80 | Élevé |
| ≥ 80 | Très élevé |

| Mode | Seuil d'alerte | Rappel | Précision |
|---|---|---|---|
| Standard | 65 | 80 % | 70 % |
| Pro | 75 | 66 % | 77 % |
| Strict | 85 | 42 % | 86 % |

## Évaluer le modèle

```bash
python ml/evaluate.py --data data/raw/shard0.parquet   # voir ml/reports/EVALUATION.md
```

## Crédits

Données : Moosavi et al., *US Accidents* (2016-2023) · © contributeurs OpenStreetMap · OSRM · Open-Meteo.
