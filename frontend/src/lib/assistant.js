import { API_URL } from "./api"

/**
 * Envoie la conversation au copilote. La réponse est un flux NDJSON (un événement JSON par ligne) :
 * text, tool (outil lancé), trip (analyse produite par un outil), error.
 * axios ne lit pas les flux dans le navigateur : fetch + ReadableStream.
 */
export async function streamChat({ messages, context, onEvent, signal }) {
  const res = await fetch(`${API_URL}/assistant/chat`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, context }),
    signal,
  })
  if (!res.ok) {
    let detail = `Erreur ${res.status}`
    try {
      const body = await res.json()
      if (typeof body.detail === "string") detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail[0]?.msg || detail
    } catch { /* corps non JSON */ }
    throw new Error(detail)
  }
  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""
  for (;;) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split("\n")
    buffer = lines.pop()
    for (const line of lines) if (line.trim()) onEvent(JSON.parse(line))
    if (done) break
  }
  if (buffer.trim()) onEvent(JSON.parse(buffer))
}

/** Résumé compact d'une analyse de trajet, envoyé au copilote comme contexte. */
export function tripContext(result, routeIndex) {
  const route = result.routes[routeIndex]
  const s = route.summary
  const pick = (d) => ({ heure: d.time, indice: d.risk_score, niveau: d.status, meteo: d.weather_label })
  return {
    type: "analyse_de_trajet",
    origine: result.origin.label,
    destination: result.destination.label,
    mode_alerte: result.mode,
    genere_le: result.generated_at,
    itineraire_affiche: routeIndex + 1,
    distance_km: route.distance_km,
    duree_min: route.duration_min,
    indice_moyen_depart_immediat: s.risk_score,
    niveau: s.risk_level,
    seuil_alerte: Math.round(s.threshold_used * 100),
    alerte: s.is_high_risk,
    troncon_le_plus_risque: { km: route.peak.km, indice: route.peak.risk_score },
    depart_immediat: pick(route.departures[0]),
    meilleur_depart: pick(route.best_departure),
    itineraires: result.routes.map((r, i) => ({
      numero: i + 1, distance_km: r.distance_km, duree_min: r.duration_min,
      indice: r.summary.risk_score, recommande: r.recommended,
    })),
    facteurs_principaux: route.explanation.factors.map((f) => ({ facteur: f.label, impact: f.impact })),
    troncons: route.segments.map((x) => ({
      km: x.km, etat_us: x.state, meteo: x.weather.weather_label,
      temperature_c: Math.round(((x.weather.Temperature_F - 32) * 5) / 9),
      nuit: x.weather.IsNight, equipements: x.road || [], indice: x.risk_score,
    })),
    alertes_officielles: (result.weather_alerts || []).map((a) => ({
      evenement: a.event, gravite: a.severity_fr, zone: a.area, fin: a.ends,
    })),
    avertissements: result.warnings,
  }
}
