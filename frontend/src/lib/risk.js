// Niveaux de risque : couleur de statut + icône + libellé (jamais la couleur seule)
export const STATUS = {
  good: { label: "Faible", icon: "●", text: "text-good", bg: "bg-good", ring: "ring-good/40", hex: "#0ca30c" },
  warning: { label: "Modéré", icon: "▲", text: "text-warning", bg: "bg-warning", ring: "ring-warning/40", hex: "#fab219" },
  serious: { label: "Élevé", icon: "◆", text: "text-serious", bg: "bg-serious", ring: "ring-serious/40", hex: "#ec835a" },
  critical: { label: "Très élevé", icon: "■", text: "text-critical", bg: "bg-critical", ring: "ring-critical/40", hex: "#d03b3b" },
}

export const LEVEL_BOUNDS = [
  { status: "good", from: 0, to: 40 },
  { status: "warning", from: 40, to: 65 },
  { status: "serious", from: 65, to: 80 },
  { status: "critical", from: 80, to: 100 },
]

export function statusOf(score) {
  if (score >= 80) return "critical"
  if (score >= 65) return "serious"
  if (score >= 40) return "warning"
  return "good"
}

export const MODES = {
  standard: { label: "Standard", hint: "Alerte dès 65 / 100 — détecte le plus de situations graves" },
  pro: { label: "Pro", hint: "Alerte dès 75 / 100 — équilibre alertes / fausses alertes" },
  strict: { label: "Strict", hint: "Alerte dès 85 / 100 — n'alerte que dans les cas les plus nets" },
}

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
