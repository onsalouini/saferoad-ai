// API simulée pour les tests de bout en bout (même forme de réponses que l'API FastAPI)
export const API = "http://api.test"

const hour = (h) => `2026-10-26T${String(h % 24).padStart(2, "0")}:00`

export function tripResult({ origin, destination, profile = "standard" }) {
  const scores = [22, 31, 58, 44, 27]
  const segments = scores.map((s, i) => ({
    lat: origin.lat + ((destination.lat - origin.lat) * i) / 4,
    lng: origin.lng + ((destination.lng - origin.lng) * i) / 4,
    km: i * 28, geometry_index: i, state: "OH", in_coverage: true,
    weather: { weather_label: i === 2 ? "Pluie" : "Ciel dégagé", Weather_Condition: i === 2 ? "Rain" : "Clear",
      Temperature_F: 55, Visibility_mi: 10, Wind_Speed_mph: 8, Precipitation_in: i === 2 ? 0.1 : 0, IsNight: false, time: hour(8) },
    road: i === 1 ? ["Feu de signalisation"] : [], road_class: i === 0 ? "local" : "freeway", road_name: i === 0 ? "Main St" : "I 70",
    heading: 80, glare: i === 3 ? { sun_elevation: 12, sun_azimuth: 95, angle_to_road: 15 } : null,
    probability: s / 100, risk_score: s, risk_level: s >= 51 ? "Élevé" : s >= 27 ? "Modéré" : "Faible",
    status: s >= 51 ? "serious" : s >= 27 ? "warning" : "good", advice: "Prudence.", mode: "standard",
    threshold_used: 0.51, is_high_risk: s >= 51,
  }))
  const departures = Array.from({ length: 24 }, (_, h) => ({
    time: hour(7 + h), risk_score: 36 - (h === 5 ? 12 : 0), peak_score: 58, status: "warning",
    weather_label: "Ciel dégagé", glare_segments: h === 0 ? 1 : 0,
  }))
  const route = {
    geometry: segments.map((s) => [s.lat, s.lng]), road_share: { freeway: 0.8, highway: 0, local: 0.2 },
    distance_km: 112, duration_min: 150,
    summary: { probability: 0.36, risk_score: 36.4, risk_level: "Modéré", status: "warning", advice: "Quelques facteurs de risque : prudence recommandée.", mode: "standard", threshold_used: 0.51, is_high_risk: false },
    peak: { risk_score: 58, km: 56 }, segments, departures, best_departure: departures[5],
    explanation: { base_logit: -0.5, factors: [{ feature: "weather", label: "Conditions météo", impact: 0.4, direction: "hausse" }] },
    coverage: 1, pauses: [{ after_min: 120, km: 90, lat: segments[3].lat, lng: segments[3].lng }],
    incidents: null, reports: [{ id: "r1", type: "nid_de_poule", label: "Nid-de-poule", lat: segments[1].lat, lng: segments[1].lng, comment: "voie de droite", created_at: hour(6), expires_at: hour(30), confirmations: 2, denials: 0 }],
    recommended: true,
  }
  return {
    origin, destination, mode: "standard", profile, profile_label: profile === "moto" ? "Moto / deux-roues" : "Voiture",
    profile_advice: profile === "moto" ? ["Soyez visible : feux allumés."] : [], threshold_used: 0.51,
    routes: [route], recommended_route: 0, weather_alerts: [], road_source: "openstreetmap", traffic_source: null,
    warnings: ["Soleil bas face à vous sur 1 tronçon(s) au départ immédiat (km 84) : risque d'éblouissement."],
    generated_at: "2026-10-26T11:00:00+00:00",
  }
}

/** Installe l'API simulée ; renvoie l'état (utilisateur connecté, requêtes reçues). */
export async function mockApi(page) {
  const state = { user: null, requests: [] }
  const json = (route, body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) })

  await page.route(`${API}/**`, async (route) => {
    const req = route.request()
    const url = new URL(req.url())
    const body = req.postData() ? JSON.parse(req.postData()) : null
    state.requests.push({ method: req.method(), path: url.pathname, body })
    switch (`${req.method()} ${url.pathname}`) {
      case "GET /model/options":
        return json(route, { levels: { warning: 0.27, serious: 0.51, critical: 0.87 }, modes: { standard: 0.51, pro: 0.7, strict: 0.87 } })
      case "GET /model/info":
        return json(route, { n_features: 95, evaluation: null })
      case "GET /auth/me":
        return state.user ? json(route, state.user) : json(route, { detail: "Authentification requise" }, 401)
      case "POST /auth/register":
        state.user = { id: "u1", name: body.name, email: body.email, email_verified: false, created_at: "2026-10-26T10:00:00Z" }
        return json(route, { token: "t", user: state.user }, 201)
      case "POST /auth/login":
        if (body.password !== "MotDePasse!123") return json(route, { detail: "E-mail ou mot de passe incorrect" }, 401)
        state.user = { id: "u1", name: "Alice", email: body.email, created_at: "2026-10-26T10:00:00Z" }
        return json(route, { token: "t", user: state.user })
      case "POST /auth/logout":
        state.user = null
        return route.fulfill({ status: 204 })
      case "GET /geo/search":
        return json(route, url.searchParams.get("q").toLowerCase().startsWith("col")
          ? [{ name: "Columbus", label: "Columbus, Ohio, États-Unis", lat: 39.9612, lng: -82.9988, country_code: "US" }]
          : [{ name: "Dayton", label: "Dayton, Ohio, États-Unis", lat: 39.7589, lng: -84.1916, country_code: "US" }])
      case "POST /predict/trip":
        return json(route, tripResult(body))
      case "GET /notifications":
        return json(route, { items: [], unread: 0 })
      case "GET /assistant/status":
        return json(route, { available: false })
      case "GET /reports/types":
        return json(route, [{ type: "nid_de_poule", label: "Nid-de-poule", hours: 720 }])
      default:
        return json(route, { detail: `non simulé : ${req.method()} ${url.pathname}` }, 404)
    }
  })
  // Pas de tuiles de carte réelles pendant les tests
  await page.route("https://tile.openstreetmap.org/**", (route) => route.fulfill({ status: 204 }))
  return state
}
