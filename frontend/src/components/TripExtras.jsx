import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import { api, errorMessage } from "../lib/api"
import { fmt } from "../lib/risk"
import { Alert, Card, Spinner } from "./ui"

/** Pauses conseillées le long de l'itinéraire, avec les aires de repos proches (chargées à la demande). */
export function PausesCard({ route }) {
  const [areas, setAreas] = useState({})
  if (!route.pauses?.length) return null

  const load = async (p, i) => {
    setAreas((a) => ({ ...a, [i]: "loading" }))
    try {
      const { data } = await api.get("/geo/rest-areas", { params: { lat: p.lat, lng: p.lng } })
      setAreas((a) => ({ ...a, [i]: data }))
    } catch (e) { setAreas((a) => ({ ...a, [i]: errorMessage(e) })) }
  }

  return (
    <Card eyebrow="Fatigue" title={`Pauses conseillées (${route.pauses.length})`}>
      <p className="text-sm text-soft">
        La vigilance baisse nettement après 2 heures de conduite : arrêtez-vous au moins 15 minutes à ces étapes.
      </p>
      <ol className="mt-4 space-y-3">
        {route.pauses.map((p, i) => (
          <li key={i} className="rounded-xl border border-line/60 bg-raised/50 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span><b className="text-ink">Pause {i + 1}</b> · après {fmt.duration(p.after_min)} de route · vers le km {p.km}</span>
              {!areas[i] && <button type="button" className="text-xs text-accent hover:underline" onClick={() => load(p, i)}>Aires à proximité</button>}
            </div>
            {areas[i] === "loading" && <div className="mt-2"><Spinner label="Recherche des aires…" /></div>}
            {typeof areas[i] === "string" && areas[i] !== "loading" && <p className="mt-2 text-xs text-serious">{areas[i]}</p>}
            {Array.isArray(areas[i]) && (
              areas[i].length
                ? <ul className="mt-2 space-y-1 text-xs text-soft">
                  {areas[i].slice(0, 4).map((a) => (
                    <li key={`${a.lat},${a.lng}`}>
                      {a.kind === "Station-service" ? "⛽" : "🅿"} {a.name} · {a.kind.toLowerCase()} · à {fmt.num(a.distance_km, 1)} km
                    </li>
                  ))}
                </ul>
                : <p className="mt-2 text-xs text-muted">Aucune aire référencée dans un rayon de 15 km.</p>
            )}
          </li>
        ))}
      </ol>
    </Card>
  )
}

/** Incidents de circulation (TomTom) et signalements des utilisateurs le long de l'itinéraire. */
export function LiveCard({ result, route, onReported }) {
  const incidents = route.incidents
  const reports = route.reports || []
  const hasAny = (incidents?.length || 0) + reports.length > 0
  return (
    <Card eyebrow="En temps réel" title="Incidents et signalements">
      {incidents === null && result.traffic_source === null && (
        <p className="text-xs text-muted">Trafic en temps réel non configuré sur le serveur (clé TomTom).</p>
      )}
      {!hasAny && <p className="text-sm text-soft">Aucun incident ni signalement sur cet itinéraire pour le moment.</p>}
      <ul className="space-y-2">
        {incidents?.map((x) => (
          <li key={x.id} className="rounded-xl border border-warning/40 bg-warning/10 px-4 py-2.5 text-sm">
            <b className="text-ink">{x.category}</b>{x.road && ` · ${x.road}`} {x.delay_min > 0 && <span className="text-soft">· +{x.delay_min} min</span>}
            {x.description && <p className="text-xs text-soft">{x.description}</p>}
          </li>
        ))}
        {reports.map((r) => <ReportItem key={r.id} report={r} onVoted={onReported} />)}
      </ul>
      <ReportForm route={route} onDone={onReported} />
    </Card>
  )
}

function ReportItem({ report, onVoted }) {
  const { user } = useAuth()
  const [state, setState] = useState(null)
  const vote = async (still) => {
    try { await api.post(`/reports/${report.id}/vote`, { still_there: still }); setState("ok"); onVoted?.() } catch (e) { setState(errorMessage(e)) }
  }
  return (
    <li className="rounded-xl border border-line/60 bg-raised/50 px-4 py-2.5 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span><b className="text-ink">{report.label}</b> · signalé {fmt.dayHour(report.created_at)}
          {report.confirmations > 0 && <span className="text-soft"> · confirmé {report.confirmations}×</span>}</span>
        {user && !state && (
          <span className="flex gap-2 text-xs">
            <button type="button" className="text-good hover:underline" onClick={() => vote(true)}>Toujours là</button>
            <button type="button" className="text-muted hover:underline" onClick={() => vote(false)}>N'est plus là</button>
          </span>
        )}
        {state && <span className="text-xs text-muted">{state === "ok" ? "Merci !" : state}</span>}
      </div>
      {report.comment && <p className="text-xs text-soft">« {report.comment} »</p>}
    </li>
  )
}

function ReportForm({ route, onDone }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [types, setTypes] = useState([])
  const [form, setForm] = useState({ type: "nid_de_poule", where: "gps", km: 0, comment: "" })
  const [state, setState] = useState(null)

  useEffect(() => { if (open && !types.length) api.get("/reports/types").then((r) => setTypes(r.data)).catch(() => {}) }, [open, types.length])

  if (!user) {
    return <p className="mt-4 text-xs text-muted"><Link to="/connexion" className="text-accent hover:underline">Connectez-vous</Link> pour signaler un danger.</p>
  }
  if (!open) return <button type="button" className="btn-ghost mt-4" onClick={() => setOpen(true)}>⚠ Signaler un danger</button>

  const position = () => new Promise((resolve, reject) => {
    if (form.where === "km") {
      const seg = route.segments.reduce((a, b) => (Math.abs(b.km - form.km) < Math.abs(a.km - form.km) ? b : a))
      resolve({ lat: seg.lat, lng: seg.lng }); return
    }
    navigator.geolocation?.getCurrentPosition((p) => resolve({ lat: p.coords.latitude, lng: p.coords.longitude }),
      () => reject(new Error("Position indisponible : choisissez un kilomètre de l'itinéraire.")), { timeout: 10000 })
  })

  const submit = async (e) => {
    e.preventDefault()
    setState("busy")
    try {
      const pos = await position()
      await api.post("/reports", { type: form.type, comment: form.comment || null, ...pos })
      setState("ok"); setOpen(false); onDone?.()
    } catch (err) { setState(err.response ? errorMessage(err) : err.message) }
  }

  return (
    <form onSubmit={submit} className="mt-4 space-y-3 rounded-xl border border-line/60 p-4">
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="rep-type">Type de danger</label>
          <select id="rep-type" className="field" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
            {types.map((t) => <option key={t.type} value={t.type}>{t.label} (visible {t.hours < 48 ? `${t.hours} h` : `${Math.round(t.hours / 24)} j`})</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="rep-where">Emplacement</label>
          <select id="rep-where" className="field" value={form.where} onChange={(e) => setForm({ ...form, where: e.target.value })}>
            <option value="gps">Ma position actuelle</option>
            <option value="km">Un kilomètre de l'itinéraire</option>
          </select>
        </div>
      </div>
      {form.where === "km" && (
        <div>
          <label className="label" htmlFor="rep-km">Kilomètre ({fmt.num(form.km, 0)})</label>
          <input id="rep-km" type="range" min={0} max={Math.round(route.distance_km)} value={form.km}
            onChange={(e) => setForm({ ...form, km: Number(e.target.value) })} className="w-full accent-[rgb(var(--accent))]" />
        </div>
      )}
      <div>
        <label className="label" htmlFor="rep-comment">Précision (facultatif)</label>
        <input id="rep-comment" className="field" maxLength={200} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} placeholder="Ex. : voie de droite, sortie 12" />
      </div>
      {state && state !== "busy" && state !== "ok" && <Alert tone="error">{state}</Alert>}
      <p className="text-xs text-muted">Ne signalez jamais en conduisant : arrêtez-vous ou demandez à un passager.</p>
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={state === "busy"}>Publier</button>
        <button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Annuler</button>
      </div>
    </form>
  )
}
