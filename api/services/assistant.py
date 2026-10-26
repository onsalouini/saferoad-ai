# api/services/assistant.py
"""
Copilote SafeRoad : assistant conversationnel qui explique les analyses du modèle,
lance lui-même des analyses (outils) et donne des conseils de conduite.

Deux fournisseurs, choisis par ASSISTANT_PROVIDER dans api/.env :
- « anthropic » (Claude, ANTHROPIC_API_KEY) ;
- « groq » (modèles open source, offre gratuite, GROQ_API_KEY ; voir services/assistant_groq.py).
Sans clé pour le fournisseur choisi, les routes répondent 503.

La réponse est diffusée en NDJSON, un événement JSON par ligne :
    {"type": "text", "text": "..."}                       morceau de réponse
    {"type": "tool", "name": "...", "label": "..."}       le copilote lance un outil
    {"type": "trip", "origin": {...}, "destination": {...}, "risk_score": ..., "status": ...}
    {"type": "error", "message": "..."}
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import AsyncIterator

import anthropic
import httpx
from anthropic import beta_async_tool

from database import db
from ml.features import WEATHER_CHOICES
from ml.predict import model_service

from . import alerts, assistant_groq, geo, weather
from .shared import RateLimiter
from .trip import TripError, analyse_trip, compact

PROVIDER = os.getenv("ASSISTANT_PROVIDER", "anthropic").lower()
CLAUDE_MODEL = os.getenv("ASSISTANT_MODEL", "claude-opus-5-5")
MODEL = assistant_groq.MODEL if PROVIDER == "groq" else CLAUDE_MODEL
PROVIDER_LABEL = {"groq": f"{assistant_groq.MODEL} via Groq", "anthropic": f"Claude ({CLAUDE_MODEL})"}.get(PROVIDER, PROVIDER)
RATE_LIMIT = int(os.getenv("ASSISTANT_RATE_LIMIT", "30"))  # messages par utilisateur et par heure
MAX_TOOL_TURNS = 6

SYSTEM = """Tu es le Copilote SafeRoad, l'assistant de sécurité routière de l'application SafeRoad AI.
Tu réponds en français, de façon claire et concrète, à des conducteurs non spécialistes.

Ce que fait SafeRoad AI :
- Un modèle LightGBM entraîné sur des accidents américains (jeu US Accidents) donne un indice de 0 à 100
  pour une situation (lieu, météo, heure, équipements routiers proches).
- L'indice estime la probabilité qu'un accident survenant dans ces conditions soit GRAVE. Ce n'est PAS la
  probabilité d'avoir un accident. Il sert surtout à comparer des horaires ou des itinéraires.
- Les niveaux (Faible, Modéré, Élevé, Très élevé) et les seuils d'alerte des modes Standard, Pro et Strict
  sont fournis dans les résultats.
- Pour un trajet, la météo prévue (Open-Meteo) est prise à l'heure de passage sur chaque tronçon, les
  équipements routiers (feux, passages piétons, ronds-points…) viennent d'OpenStreetMap, les alertes
  officielles du National Weather Service, et 24 heures de départ sont comparées.
- Hors des États-Unis, les résultats sont seulement indicatifs.
- Les « facteurs » sont des contributions SHAP : un impact positif fait monter le score.

Outils : quand l'utilisateur parle d'un trajet ou d'un lieu qui n'est pas déjà analysé, utilise les outils
(analyser_trajet, conditions_actuelles, simuler_scenario) plutôt que de deviner. Ne lance pas d'outil pour une
question générale de sécurité routière.

Quand une analyse est fournie entre balises <analyse> ou renvoyée par un outil, appuie-toi uniquement sur ses
chiffres, cite-les, et n'invente aucune donnée (trafic, travaux, accidents en cours) que tu n'as pas.
Si l'utilisateur demande quelque chose que les données ne contiennent pas, dis-le simplement.

Forme des réponses : paragraphes courts, listes à puces avec « - » quand c'est utile, gras avec **...**
pour l'essentiel. Pas de titres, pas de tableaux. Reste bref : 150 mots environ sauf demande contraire.
Pour un briefing de trajet : verdict en une phrase, puis le meilleur créneau, les points de vigilance
(tronçons, météo, nuit, alertes officielles) et 2 ou 3 conseils de conduite adaptés.

Tu ne remplaces pas la vigilance du conducteur ni les consignes officielles. En cas d'alerte météo
officielle ou d'urgence, renvoie vers les autorités et les services d'urgence."""

TOOL_LABELS = {
    "analyser_trajet": "Analyse du trajet",
    "conditions_actuelles": "Météo et risque actuels",
    "simuler_scenario": "Simulation d'un scénario",
}

_client: anthropic.AsyncAnthropic | None = None
limiter = RateLimiter("assistant", RATE_LIMIT, 3600)


def available() -> bool:
    if PROVIDER == "groq":
        return assistant_groq.available()
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


def _system(context: dict | None) -> list[dict]:
    blocks = [{"type": "text", "text": SYSTEM}]
    if context:
        data = json.dumps(context, ensure_ascii=False, sort_keys=True)
        blocks.append({"type": "text", "text": f"<analyse>\n{data}\n</analyse>"})
    return blocks


async def _place(query: str) -> dict:
    found = await geo.search(query, limit=1)
    if not found:
        raise ValueError(f"Lieu introuvable : « {query} ». Demande une adresse plus précise.")
    p = found[0]
    return {"lat": p["lat"], "lng": p["lng"], "label": p["name"]}


def _make_tools(events: list[dict]):
    """Outils du copilote. `events` reçoit les événements à diffuser au frontend."""

    @beta_async_tool
    async def analyser_trajet(depart: str, arrivee: str, mode: str = "standard", profil: str = "standard") -> str:
        """Analyse complète d'un trajet routier : itinéraires, risque par tronçon avec la météo prévue au passage,
        équipements routiers, alertes officielles et meilleure heure de départ sur 24 h.

        Args:
            depart: Lieu de départ (ville ou adresse), ex. « Dayton, Ohio ».
            arrivee: Lieu d'arrivée (ville ou adresse), ex. « Columbus, Ohio ».
            mode: Mode d'alerte : « standard », « pro » ou « strict ».
            profil: Conducteur / véhicule : « standard » (voiture), « moto », « poids_lourd » ou « jeune ».
        """
        try:
            o, d = await _place(depart), await _place(arrivee)
            result = await analyse_trip(o, d, mode if mode in ("standard", "pro", "strict") else "standard",
                                        profile=profil if profil in ("standard", "moto", "poids_lourd", "jeune") else "standard")
        except (ValueError, TripError, httpx.HTTPError) as e:
            return json.dumps({"erreur": getattr(e, "message", None) or str(e) or "service indisponible"}, ensure_ascii=False)
        summary = compact(result)
        events.append({"type": "trip", "origin": o, "destination": d, "mode": result["mode"],
                       "risk_score": summary["indice_moyen_depart_immediat"], "level": summary["niveau"],
                       "best_departure": summary["meilleur_depart"]["heure"]})
        return json.dumps(summary, ensure_ascii=False)

    @beta_async_tool
    async def conditions_actuelles(lieu: str) -> str:
        """Météo actuelle, alertes officielles et indice de risque pour une situation standard (route sans
        équipement particulier) en un lieu, maintenant.

        Args:
            lieu: Ville ou adresse, ex. « Miami, Florida ».
        """
        try:
            p = await _place(lieu)
            w = await weather.current(p["lat"], p["lng"])
        except (ValueError, httpx.HTTPError) as e:
            return json.dumps({"erreur": str(e) or "service indisponible"}, ensure_ascii=False)
        state = geo.state_at(p["lat"], p["lng"])
        result = model_service.predict_one({**w, "Start_Lat": p["lat"], "Start_Lng": p["lng"], "State": state or ""})
        official = await alerts.active_alerts([(p["lat"], p["lng"])]) if state else []
        return json.dumps({
            "lieu": p["label"], "etat_us": state, "hors_usa": state is None, "heure_locale": w["time"],
            "meteo": w["weather_label"], "temperature_c": round((w["Temperature_F"] - 32) * 5 / 9),
            "visibilite_km": round(w["Visibility_mi"] * 1.609, 1), "vent_kmh": round(w["Wind_Speed_mph"] * 1.609),
            "precipitations_mm": round(w["Precipitation_in"] * 25.4, 1), "nuit": w["IsNight"],
            "indice": result["risk_score"], "niveau": result["risk_level"],
            "facteurs": [{"facteur": f["label"], "impact": f["impact"]} for f in result["explanation"]["factors"][:5]],
            "alertes_officielles": [{"evenement": a["event"], "gravite": a["severity_fr"]} for a in official or []],
        }, ensure_ascii=False)

    @beta_async_tool
    async def simuler_scenario(lieu: str, condition_meteo: str, heure: int, temperature_c: float = 15,
                               visibilite_km: float = 16, precipitations_mm: float = 0, vent_kmh: float = 10,
                               intersection: bool = False, feu: bool = False) -> str:
        """Indice de risque pour un scénario hypothétique en un lieu (« et si je partais à 23 h sous la pluie ? »).

        Args:
            lieu: Ville ou adresse.
            condition_meteo: Une des catégories : Clear, Fair, Fair / Windy, Partly Cloudy, Mostly Cloudy, Cloudy,
                Overcast, Scattered Clouds, Haze, Fog, Light Drizzle, Light Rain, Rain, Heavy Rain, Light Snow, Other.
            heure: Heure locale de 0 à 23.
            temperature_c: Température en °C.
            visibilite_km: Visibilité en km (16 = très bonne).
            precipitations_mm: Précipitations en mm par heure.
            vent_kmh: Vent en km/h.
            intersection: Présence d'une intersection.
            feu: Présence d'un feu de signalisation.
        """
        try:
            p = await _place(lieu)
        except (ValueError, httpx.HTTPError) as e:
            return json.dumps({"erreur": str(e) or "service indisponible"}, ensure_ascii=False)
        if condition_meteo not in WEATHER_CHOICES:
            return json.dumps({"erreur": f"Catégorie météo inconnue. Valeurs possibles : {', '.join(WEATHER_CHOICES)}"},
                              ensure_ascii=False)
        h = min(23, max(0, int(heure)))
        now = datetime.now()
        state = geo.state_at(p["lat"], p["lng"])
        result = model_service.predict_one({
            "Start_Lat": p["lat"], "Start_Lng": p["lng"], "State": state or "",
            "Temperature_F": temperature_c * 9 / 5 + 32, "Humidity": 70, "Pressure": 29.9,
            "Visibility_mi": visibilite_km / 1.609, "Wind_Speed_mph": vent_kmh / 1.609,
            "Precipitation_in": precipitations_mm / 25.4, "Weather_Condition": condition_meteo,
            "Hour": h, "Month": now.month, "DayOfWeek": now.weekday(),
            "Junction": intersection, "Traffic_Signal": feu,
        })
        return json.dumps({
            "lieu": p["label"], "hors_usa": state is None, "indice": result["risk_score"],
            "niveau": result["risk_level"],
            "facteurs": [{"facteur": f["label"], "impact": f["impact"]} for f in result["explanation"]["factors"][:5]],
        }, ensure_ascii=False)

    return [analyser_trajet, conditions_actuelles, simuler_scenario]


def _event(kind: str, **data) -> str:
    return json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n"


async def _track(user_id: str | None, usage) -> None:
    """Cumule la consommation du copilote par utilisateur et par mois (suivi des coûts)."""
    if not user_id or usage is None:
        return
    month = datetime.now().strftime("%Y-%m")
    if isinstance(usage, dict):  # Groq (format OpenAI)
        tokens_in, tokens_out = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
    else:  # Claude
        tokens_in = int(getattr(usage, "input_tokens", 0) or 0) + int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)
    await db().increment(user_id, ["assistant_usage", month], {
        "input_tokens": int(tokens_in or 0), "output_tokens": int(tokens_out or 0), "requests": 1,
    })


async def stream_reply(messages: list[dict], context: dict | None, user_id: str | None = None) -> AsyncIterator[str]:
    """Événements NDJSON de la réponse, au fil de l'eau. Les erreurs sont renvoyées dans le flux."""
    events: list[dict] = []
    tools = _make_tools(events) if model_service.ready else []
    if PROVIDER == "groq":
        async for line in _stream_groq(messages, context, user_id, tools, events):
            yield line
        return
    try:
        runner = _get_client().beta.messages.tool_runner(
            model=MODEL,
            max_tokens=16000,
            system=_system(context),
            messages=messages,
            tools=tools,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_iterations=MAX_TOOL_TURNS,
            stream=True,
        )
        async for stream in runner:
            while events:
                e = events.pop(0)
                yield _event(e.pop("type"), **e)
            async for text in stream.text_stream:
                yield _event("text", text=text)
            final = await stream.get_final_message()
            await _track(user_id, final.usage)
            for block in final.content:
                if block.type == "tool_use":
                    yield _event("tool", name=block.name, label=TOOL_LABELS.get(block.name, block.name))
            if final.stop_reason == "refusal":
                yield _event("text", text="\n\nJe ne peux pas répondre à cette demande. Reformulez-la autour de votre trajet ou de la sécurité routière.")
                break
            if final.stop_reason == "max_tokens":
                yield _event("text", text="\n\n(Réponse tronquée.)")
                break
        while events:
            e = events.pop(0)
            yield _event(e.pop("type"), **e)
    except anthropic.AuthenticationError:
        yield _event("error", message="Le copilote est mal configuré (clé API invalide). Contactez l'administrateur.")
    except anthropic.RateLimitError:
        yield _event("error", message="Le copilote est très sollicité. Réessayez dans un instant.")
    except anthropic.APIConnectionError:
        yield _event("error", message="Impossible de joindre le service d'IA. Vérifiez la connexion du serveur.")
    except anthropic.APIStatusError as e:
        print(f"Erreur Claude API {e.status_code} : {e.message}")
        yield _event("error", message="Le copilote a rencontré une erreur. Réessayez dans un instant.")


async def _stream_groq(messages: list[dict], context: dict | None, user_id: str | None, tools, events) -> AsyncIterator[str]:
    system = "\n\n".join(b["text"] for b in _system(context))
    try:
        async for line, usage in assistant_groq.stream(system, messages, tools, TOOL_LABELS, MAX_TOOL_TURNS, _event, events):
            if usage:
                await _track(user_id, usage)
            if line:
                yield line
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        print(f"Erreur Groq {code} : {e}")
        if code == 429:
            yield _event("error", message="Le copilote est très sollicité (limite gratuite Groq). Réessayez dans une minute.")
        elif code in (401, 403):
            yield _event("error", message="Le copilote est mal configuré (clé Groq invalide). Contactez l'administrateur.")
        else:
            yield _event("error", message="Le copilote a rencontré une erreur. Réessayez dans un instant.")
    except httpx.HTTPError as e:
        print(f"Groq injoignable : {e}")
        yield _event("error", message="Impossible de joindre le service d'IA. Vérifiez la connexion du serveur.")
