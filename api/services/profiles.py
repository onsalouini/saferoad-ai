# api/services/profiles.py
"""
Profils de conducteur / véhicule.

Le modèle ne connaît pas le véhicule (US Accidents ne le renseigne pas) : les profils n'en changent
pas le score. Ils abaissent le seuil d'alerte (alerte plus précoce pour les usagers vulnérables) et
ajoutent des conseils et des vérifications spécifiques. Ce sont des règles de prudence, pas des
résultats appris : elles sont présentées comme telles dans l'interface.
"""
from __future__ import annotations

PROFILES = {
    "standard": {
        "label": "Voiture",
        "threshold_delta": 0.0,
        "advice": [],
    },
    "moto": {
        "label": "Moto / deux-roues",
        "threshold_delta": -0.10,
        "advice": [
            "Pluie ou chaussée humide : freinez plus tôt et évitez les marquages au sol et les plaques d'égout.",
            "Vent latéral : anticipez les rafales en sortie de pont, de tranchée ou en dépassant un poids lourd.",
            "Soyez visible : feux allumés, équipement clair ou réfléchissant, surtout de nuit.",
        ],
        "wind_kmh": 50,
        "cold_c": 3,
    },
    "poids_lourd": {
        "label": "Poids lourd",
        "threshold_delta": -0.05,
        "advice": [
            "Vent fort : risque de renversement à vide ou en charge haute ; réduisez la vitesse sur les viaducs.",
            "Distances de freinage allongées sous la pluie : gardez au moins 50 m avec le véhicule qui précède.",
            "Respectez les temps de conduite : pause de 45 min toutes les 4 h 30 (réglementation européenne).",
        ],
        "wind_kmh": 60,
        "pause_every_min": 270,
    },
    "jeune": {
        "label": "Jeune conducteur",
        "threshold_delta": -0.08,
        "advice": [
            "Nuit et pluie cumulent les risques : si possible, choisissez un créneau de jour.",
            "Pas de téléphone au volant, même à l'arrêt dans les embouteillages.",
            "Gardez de la marge : 2 secondes au moins avec le véhicule qui précède, 3 sous la pluie.",
        ],
    },
}


def threshold(base: float, profile: str) -> float:
    return round(max(0.05, base + PROFILES.get(profile, PROFILES["standard"])["threshold_delta"]), 4)


def checks(profile: str, segments: list[dict]) -> list[str]:
    """Avertissements propres au profil, à partir de la météo des tronçons."""
    p = PROFILES.get(profile, PROFILES["standard"])
    out = []
    if "wind_kmh" in p:
        windy = [s for s in segments if s["weather"]["Wind_Speed_mph"] * 1.609 >= p["wind_kmh"]]
        if windy:
            out.append(f"Vent fort (≥ {p['wind_kmh']} km/h) prévu sur {len(windy)} tronçon(s) : vigilance particulière "
                       f"pour un {p['label'].lower()}.")
    if "cold_c" in p:
        cold = [s for s in segments if (s["weather"]["Temperature_F"] - 32) * 5 / 9 <= p["cold_c"]]
        if cold:
            out.append(f"Température ≤ {p['cold_c']} °C sur {len(cold)} tronçon(s) : risque de verglas, adhérence réduite.")
    return out
