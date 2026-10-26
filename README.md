# SafeRoad AI

Plateforme d'IA qui estime le risque d'un trajet routier à partir de l'historique des accidents, de la météo
prévue, des équipements routiers et de l'itinéraire, puis **recommande l'itinéraire et l'heure de départ les plus sûrs**.

* **Analyse de trajet** : itinéraire réel (OSRM), météo prévue à l'heure de passage sur chaque tronçon
  (Open-Meteo), équipements routiers réels autour de chaque tronçon (OpenStreetMap / Overpass), alertes météo
  officielles (National Weather Service), comparaison des itinéraires et meilleur créneau de départ sur 24 h.
* **Copilote IA** (Claude) : briefing du trajet en langage clair, réponses aux questions de conduite, et
  **outils** qui lui permettent de lancer lui-même une analyse de trajet, de consulter les conditions actuelles
  d'un lieu ou de simuler un scénario (« et si je partais à 23 h sous la pluie ? »). Dictée et lecture vocales.
* **Alertes de départ** : enregistrez un trajet régulier (heure, jours, fuseau). Il est analysé
  automatiquement dans l'heure qui précède le départ : notification dans l'application (et du navigateur),
  e-mail si le risque dépasse le seuil ou si une alerte officielle est en cours.
* **Mode conduite** : plein écran épuré, résumé lu à voix haute, écran maintenu allumé.
* **Profils** voiture, moto, poids lourd, jeune conducteur : alerte plus précoce et vérifications dédiées
  (vent, froid, temps de conduite). Règles de prudence : le modèle ne connaît pas le véhicule.
* **Soleil éblouissant** : position du soleil à l'heure de passage comparée à la direction de la route.
* **Pauses fatigue** toutes les 2 h (4 h 30 en poids lourd) avec les aires de repos proches (OpenStreetMap).
* **Signalements communautaires** (nid-de-poule, verglas, accident…) visibles sur la carte, confirmés ou
  retirés par les votes ; **incidents de circulation** en temps réel (TomTom, avec clé).
* **Notifications push** (Web Push), même application fermée.
* **Application installable (PWA)**, utilisable hors ligne pour la coquille, géolocalisation du départ.
* **Simulateur** et **transparence du modèle** (performances, calibration, tests de cohérence, limites).
* **Comptes** : cookie de session httpOnly, limitation des tentatives de connexion, mot de passe oublié,
  vérification de l'e-mail, export et suppression des données (RGPD), suivi de la consommation du copilote.

> ⚠️ Le modèle a été entraîné sur des accidents **américains** (US Accidents). Il estime la probabilité qu'un
> accident survenant dans des conditions données soit **grave**, pas la probabilité qu'il survienne. Hors des
> États-Unis, les résultats sont indicatifs. Voir [EVALUATION.md](ml/reports/EVALUATION.md).

## Modèle v3

| | v2 | **v3** |
|---|---|---|
| Variable `Distance(mi)` (fuite de données) | utilisée | **retirée** |
| Évaluation | fragment possiblement vu à l'entraînement | **année 2022 jamais vue** (split temporel) |
| ROC-AUC sur 2022 | 0,881 | **0,900** |
| Score de Brier (plus bas = mieux) | 0,160 | **0,121** |
| Score moyen prédit / observé | 48,5 % / 33,5 % | **34,5 % / 33,5 %** (recalibration de Platt) |

**v4 (prête, pas encore entraînée)** : `ml/train.py` ajoute le **type de route** (autoroute / route / rue, tiré
du nom de la rue à l'entraînement et des étapes OSRM à l'analyse), des **contraintes monotones** (pluie,
visibilité, nuit, brouillard, neige ne peuvent pas faire baisser le score) et un entraînement sur les
**7 fragments** du jeu de données. Il faut au moins 12 à 16 Go de RAM pour l'entraîner en un temps raisonnable.
Le modèle en service reste la **v3** ; l'API détecte la version chargée et utilise le type de route dès
qu'un modèle v4 est présent.

Réentraîner : télécharger les fragments dans `data/raw/shard0..6.parquet`, puis `python ml/train.py`
(le modèle précédent est sauvegardé en `saferoad_model_v<n>.pkl`) et `python ml/evaluate.py --years 2022 2023`.
Sur une machine de 6 Go, l'entraînement à 2 M d'accidents (`--per-shard 280000`) dépasse 1 h ; réduire `--per-shard` ou utiliser une machine plus puissante (ou Google Colab).

## Architecture

```
saferoad-ai/
├── api/                          FastAPI
│   ├── main.py                   application, CORS, planificateur, routes système et modèle
│   ├── ml/features.py            encodage des variables (partagé avec l'entraînement et l'évaluation)
│   ├── ml/predict.py             chargement du modèle, prédiction, explication SHAP, niveaux
│   ├── ml/calibrated.py          LightGBM + recalibration de Platt
│   ├── services/trip.py          analyse de trajet (partagée : API, copilote, alertes)
│   ├── services/geo.py           Nominatim (débit limité, cache), OSRM (cache), détection de l'État US
│   ├── services/weather.py       Open-Meteo
│   ├── services/overpass.py      équipements routiers OpenStreetMap
│   ├── services/alerts.py        alertes officielles NWS
│   ├── services/assistant.py     copilote IA (Claude API, outils, flux NDJSON)
│   ├── services/scheduler.py     alertes de départ
│   ├── services/mailer.py        e-mails SMTP (console si non configuré)
│   ├── routes/                   predict, geo, auth, history, trips, assistant
│   ├── database.py               MongoDB (MONGO_URI) ou fichier JSON local
│   ├── auth.py                   bcrypt, JWT en cookie httpOnly, limitation des tentatives
│   └── tests/                    pytest
├── ml/
│   ├── train.py                  réentraînement (v3)
│   ├── evaluate.py               évaluation de la fiabilité
│   └── reports/                  training.json, evaluation.json, EVALUATION.md
├── frontend/                     React 19 + Vite + Tailwind + Leaflet (PWA)
├── docker-compose.yml            MongoDB + API + frontend
└── .github/workflows/ci.yml      tests, lint, build, images Docker
```

Services externes, **gratuits et sans clé** : OpenStreetMap, Nominatim, OSRM, Overpass, Open-Meteo, NWS.
Clé facultative : Claude API (copilote).

## Installation

Prérequis : Python 3.11+ et Node 20.19+.

```bash
# 1. Backend
python -m venv venv
venv\Scripts\activate            # Windows  (Linux/macOS : source venv/bin/activate)
pip install -r requirements-dev.txt
copy api\.env.example api\.env   # définir JWT_SECRET ; ANTHROPIC_API_KEY, SMTP_*, MONGO_URI sont optionnels

# 2. Placer le modèle dans ml/models/saferoad_model.pkl (ou le réentraîner : python ml/train.py)

# 3. Lancer l'API
cd api
uvicorn main:app --reload --port 8000     # documentation : http://localhost:8000/docs
python -m pytest -q                       # tests (53)

# 4. Frontend (autre terminal)
cd frontend
npm install
npm run dev                                # http://localhost:5173
npm run test:e2e                           # tests de bout en bout (Playwright, API simulée)
```

Déploiement : [render.yaml](render.yaml) (Render Blueprint : API Docker + frontend statique). Le modèle se
place sur le disque persistant ou se télécharge au démarrage via `MODEL_URL`.

Ou avec Docker : `docker compose up --build` (frontend sur http://localhost:8080).

Sans `MONGO_URI`, les données sont enregistrées dans `api/data/local_db.json`. Sans `SMTP_HOST`, les e-mails
(réinitialisation, alertes) s'affichent dans la console de l'API. Sans `ANTHROPIC_API_KEY`, le copilote est désactivé.

**Production** : `COOKIE_SECURE=true` (HTTPS), un seul worker uvicorn (le planificateur tourne dans le
processus), et des instances auto-hébergées d'OSRM, Nominatim et Overpass (`OSRM_URL`, `NOMINATIM_URL`,
`OVERPASS_URL`) : les instances publiques limitent le débit et sont parfois saturées. Si Overpass ne répond
pas en 12 s, l'analyse continue sans les équipements routiers et le signale.

## API

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | état de l'API, du modèle, de la base, du copilote, des e-mails |
| GET | `/model/info`, `/model/options` | métadonnées, rapports, seuils et niveaux |
| POST | `/predict` | simulation manuelle : score, niveau, facteurs explicatifs |
| POST | `/predict/trip` | analyse de trajet complète |
| GET | `/geo/search`, `/geo/reverse`, `/weather` | adresses et météo actuelle |
| POST | `/auth/register`, `/auth/login`, `/auth/logout` | comptes (cookie de session) · `GET /auth/me` |
| POST | `/auth/forgot`, `/auth/reset` | mot de passe oublié |
| GET / DELETE | `/history`, `/history/{id}` | historique |
| GET / POST / DELETE | `/trips`, `/trips/{id}`, `POST /trips/{id}/check` | trajets enregistrés (alertes) |
| GET / POST | `/notifications`, `/notifications/read-all`, `/notifications/{id}/read` | notifications |
| GET / POST | `/assistant/status`, `/assistant/chat`, `/assistant/usage` | copilote IA (flux NDJSON, connexion requise) |
| GET | `/geo/rest-areas` | aires de repos et stations autour d'un point |
| GET / POST | `/reports`, `/reports/types`, `/reports/{id}/vote` | signalements communautaires |
| GET / POST / DELETE | `/push/public-key`, `/push/subscribe`, `/push/test` | notifications push |
| POST | `/auth/verify/send`, `/auth/verify` | vérification de l'e-mail |
| GET / POST | `/account/export`, `/account/delete` | données personnelles (RGPD) |
