import { useEffect } from "react"
import { STATUS, fmt } from "../lib/risk"
import { speak, speechSupported, stopSpeaking } from "../lib/voice"

/** Résumé parlé de l'analyse, généré localement (sans IA). */
function summaryText(result, route) {
  const s = route.summary
  const best = route.best_departure
  const now = route.departures[0]
  const risky = route.segments.filter((x) => x.status === "serious" || x.status === "critical")
  const parts = [
    `Trajet ${result.origin.label || ""} vers ${result.destination.label || ""} : ${Math.round(route.distance_km)} kilomètres, environ ${fmt.duration(route.duration_min)}.`,
    `Indice de risque ${Math.round(s.risk_score)} sur 100, niveau ${s.risk_level.toLowerCase()}.`,
    now.risk_score - best.risk_score >= 1
      ? `Le créneau le plus sûr est ${fmt.dayHour(best.time)}, avec ${Math.round(now.risk_score - best.risk_score)} points de moins.`
      : "Partir maintenant est le meilleur créneau des prochaines 24 heures.",
  ]
  if (risky.length) parts.push(`Vigilance au kilomètre ${risky.map((x) => Math.round(x.km)).join(", ")}.`)
  for (const a of (result.weather_alerts || []).slice(0, 2)) parts.push(`Alerte officielle : ${a.event}.`)
  parts.push("Bonne route, restez prudent.")
  return parts.join(" ")
}

/** Plein écran épuré pour consulter le trajet d'un coup d'œil (à l'arrêt). */
export default function DrivingMode({ result, route, onClose }) {
  const s = route.summary
  const st = STATUS[s.status]
  const upcoming = route.segments.filter((x) => x.status !== "good").slice(0, 4)

  useEffect(() => {
    let lock
    navigator.wakeLock?.request("screen").then((l) => { lock = l }).catch(() => {})
    const onKey = (e) => e.key === "Escape" && onClose()
    window.addEventListener("keydown", onKey)
    document.body.style.overflow = "hidden"
    return () => {
      lock?.release().catch(() => {})
      window.removeEventListener("keydown", onKey)
      document.body.style.overflow = ""
      stopSpeaking()
    }
  }, [onClose])

  return (
    <div role="dialog" aria-modal="true" aria-label="Mode conduite" className="fixed inset-0 z-[2000] flex flex-col bg-page px-5 py-6 sm:px-10">
      <div className="flex items-center justify-between">
        <p className="eyebrow">Mode conduite · {result.origin.label} → {result.destination.label}</p>
        <button type="button" onClick={onClose} className="btn-ghost px-5 py-3 text-base">Fermer ✕</button>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center text-center">
        <p className="text-lg text-soft">Indice de risque</p>
        <p className={`mt-2 text-[7rem] font-bold leading-none tnum sm:text-[10rem] ${st.text}`}>{Math.round(s.risk_score)}</p>
        <p className="mt-3 text-3xl font-semibold">{st.icon} {s.risk_level}</p>
        <p className="mt-6 max-w-xl text-xl text-soft">{s.advice}</p>

        <div className="mt-10 grid w-full max-w-3xl gap-4 sm:grid-cols-2">
          <div className="card px-6 py-5 text-left">
            <p className="text-sm text-muted">Meilleur départ</p>
            <p className="mt-1 text-3xl font-bold tnum">{fmt.dayHour(route.best_departure.time)}</p>
            <p className="text-soft">indice {fmt.num(route.best_departure.risk_score, 0)} · {route.best_departure.weather_label.toLowerCase()}</p>
          </div>
          <div className="card px-6 py-5 text-left">
            <p className="text-sm text-muted">Points de vigilance</p>
            {upcoming.length
              ? upcoming.map((x) => <p key={x.km} className="mt-1 text-lg">km {fmt.num(x.km, 0)} · {x.weather.weather_label.toLowerCase()} · <b>{Math.round(x.risk_score)}</b></p>)
              : <p className="mt-1 text-lg text-good">Aucun tronçon à risque marqué</p>}
          </div>
        </div>
        {(result.weather_alerts || []).length > 0 && (
          <p className="mt-6 rounded-xl border border-critical/50 bg-critical/10 px-5 py-3 text-lg">
            ⚠ {result.weather_alerts[0].event} ({result.weather_alerts[0].severity_fr})
          </p>
        )}
      </div>

      <div className="flex flex-wrap justify-center gap-3">
        {speechSupported && (
          <>
            <button type="button" onClick={() => speak(summaryText(result, route))} className="btn-primary px-8 py-4 text-lg">🔊 Lire le résumé</button>
            <button type="button" onClick={stopSpeaking} className="btn-ghost px-6 py-4 text-lg">Stop</button>
          </>
        )}
      </div>
      <p className="mt-4 text-center text-xs text-muted">Ne manipulez pas votre téléphone en conduisant : consultez ce résumé à l'arrêt ou faites-le lire à voix haute.</p>
    </div>
  )
}
