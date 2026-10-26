// Niveaux de risque : couleur de statut + icône + libellé (jamais la couleur seule)
export const STATUS = {
  good: { label: "Faible", icon: "●", text: "text-good", bg: "bg-good", ring: "ring-good/40", hex: "#0ca30c" },
  warning: { label: "Modéré", icon: "▲", text: "text-warning", bg: "bg-warning", ring: "ring-warning/40", hex: "#fab219" },
  serious: { label: "Élevé", icon: "◆", text: "text-serious", bg: "bg-serious", ring: "ring-serious/40", hex: "#ec835a" },
  critical: { label: "Très élevé", icon: "■", text: "text-critical", bg: "bg-critical", ring: "ring-critical/40", hex: "#d03b3b" },
}

// Bornes des niveaux et seuils des modes : valeurs par défaut (modèle v2), remplacées au démarrage
// par celles du modèle chargé (GET /model/options, voir configureLevels dans main.jsx).
export const LEVEL_BOUNDS = [
  { status: "good", from: 0, to: 40 },
  { status: "warning", from: 40, to: 65 },
  { status: "serious", from: 65, to: 80 },
  { status: "critical", from: 80, to: 100 },
]

export function statusOf(score) {
  for (let i = LEVEL_BOUNDS.length - 1; i > 0; i--) {
    if (score >= LEVEL_BOUNDS[i].from) return LEVEL_BOUNDS[i].status
  }
  return "good"
}

const MODE_HINTS = {
  standard: "détecte le plus de situations graves",
  pro: "équilibre alertes / fausses alertes",
  strict: "n'alerte que dans les cas les plus nets",
}

export const MODES = {
  standard: { label: "Standard", hint: `Alerte dès 65 / 100 — ${MODE_HINTS.standard}` },
  pro: { label: "Pro", hint: `Alerte dès 75 / 100 — ${MODE_HINTS.pro}` },
  strict: { label: "Strict", hint: `Alerte dès 85 / 100 — ${MODE_HINTS.strict}` },
}

/** Applique les seuils du modèle chargé côté API ({ levels: {warning, serious, critical}, modes: {...} }). */
export function configureLevels({ levels, modes } = {}) {
  if (levels) {
    const b = [0, levels.warning * 100, levels.serious * 100, levels.critical * 100, 100].map((x) => Math.round(x))
    LEVEL_BOUNDS.forEach((lvl, i) => { lvl.from = b[i]; lvl.to = b[i + 1] })
  }
  for (const [k, t] of Object.entries(modes || {})) {
    if (MODES[k]) MODES[k].hint = `Alerte dès ${Math.round(t * 100)} / 100 — ${MODE_HINTS[k]}`
  }
}

// Profils conducteur / véhicule : règles de prudence (alerte plus précoce), le modèle ne connaît pas le véhicule
export const PROFILES = {
  standard: { label: "Voiture", icon: "🚗", hint: "Seuils d'alerte du mode choisi." },
  moto: { label: "Moto / deux-roues", icon: "🏍", hint: "Alerte 10 points plus tôt ; vérifications vent et froid." },
  poids_lourd: { label: "Poids lourd", icon: "🚚", hint: "Alerte 5 points plus tôt ; vent, pauses toutes les 4 h 30." },
  jeune: { label: "Jeune conducteur", icon: "🔰", hint: "Alerte 8 points plus tôt ; conseils adaptés." },
}

export const ROAD_CLASS_FR = { freeway: "Autoroute", highway: "Route", local: "Rue" }

export const WEATHER_FR = {
  Clear: "Dégagé", Fair: "Beau temps", "Fair / Windy": "Beau temps venteux", "Partly Cloudy": "Partiellement nuageux",
  "Mostly Cloudy": "Très nuageux", "Scattered Clouds": "Nuages épars", Cloudy: "Nuageux", Overcast: "Couvert",
  Fog: "Brouillard", Haze: "Brume", "Light Drizzle": "Bruine", "Light Rain": "Pluie faible", Rain: "Pluie",
  "Heavy Rain": "Pluie forte", "Light Snow": "Neige faible", Other: "Autre (orage, neige forte, verglas…)",
}

export const DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

export const fmt = {
  pct: (x, d = 1) => `${(x * 100).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d })} %`,
  num: (x, d = 1) => Number(x).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: d }),
  int: (x) => Number(x).toLocaleString("fr-FR"),
  hour: (iso) => new Date(iso).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }),
  dayHour: (iso) => new Date(iso).toLocaleString("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" }),
  date: (iso) => new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }),
  duration: (min) => (min >= 60 ? `${Math.floor(min / 60)} h ${String(min % 60).padStart(2, "0")}` : `${min} min`),
  fToC: (f) => Math.round(((f - 32) * 5) / 9),
  miToKm: (mi) => Math.round(mi * 1.609 * 10) / 10,
  mphToKmh: (mph) => Math.round(mph * 1.609),
  inToMm: (i) => Math.round(i * 25.4 * 10) / 10,
}
