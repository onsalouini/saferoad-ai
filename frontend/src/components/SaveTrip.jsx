import { useState } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import { api, errorMessage } from "../lib/api"
import { DAYS_FR } from "../lib/risk"
import { Alert } from "./ui"

const browserTz = () => {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC" } catch { return "UTC" }
}

/** Formulaire « Recevoir des alertes pour ce trajet » (trajet enregistré). */
export default function SaveTrip({ origin, destination, mode, profile = "standard" }) {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [time, setTime] = useState("08:00")
  const [days, setDays] = useState([0, 1, 2, 3, 4])
  const [email, setEmail] = useState(true)
  const [state, setState] = useState(null)

  if (!user) {
    return (
      <p className="text-sm text-soft">
        <Link to="/connexion" state={{ from: "/trajet" }} className="text-accent hover:underline">Connectez-vous</Link> pour
        enregistrer ce trajet et recevoir une alerte avant chaque départ.
      </p>
    )
  }
  if (state === "ok") {
    return (
      <Alert tone="info" title="Trajet enregistré">
        Vous recevrez une notification dans l'heure qui précède chaque départ. <Link to="/mes-trajets" className="text-accent hover:underline">Gérer mes trajets →</Link>
      </Alert>
    )
  }
  if (!open) {
    return <button type="button" onClick={() => setOpen(true)} className="btn-ghost">🔔 Recevoir des alertes pour ce trajet</button>
  }

  const toggleDay = (d) => setDays((x) => (x.includes(d) ? x.filter((y) => y !== d) : [...x, d].sort()))
  const save = async (e) => {
    e.preventDefault()
    setState("busy")
    try {
      await api.post("/trips", { origin, destination, mode, profile, departure_time: time, days, tz: browserTz(), notify_email: email })
      setState("ok")
    } catch (err) { setState(errorMessage(err)) }
  }

  return (
    <form onSubmit={save} className="space-y-4">
      <div className="flex flex-wrap items-end gap-4">
        <div>
          <label className="label" htmlFor="dep-time">Heure habituelle de départ</label>
          <input id="dep-time" type="time" required value={time} onChange={(e) => setTime(e.target.value)} className="field w-32" />
        </div>
        <fieldset>
          <legend className="label">Jours</legend>
          <div className="flex gap-1">
            {DAYS_FR.map((d, i) => (
              <button key={d} type="button" onClick={() => toggleDay(i)} aria-pressed={days.includes(i)}
                className={`h-9 w-10 rounded-lg text-xs font-semibold transition ${days.includes(i) ? "bg-accent-strong text-white" : "bg-raised text-soft hover:text-ink"}`}>
                {d.slice(0, 2)}
              </button>
            ))}
          </div>
        </fieldset>
      </div>
      <label className="flex items-center gap-2 text-sm text-soft">
        <input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--accent))]" />
        M'envoyer aussi un e-mail si le risque est élevé ou si une alerte météo officielle est en cours
      </label>
      {state && state !== "busy" && <Alert tone="error">{state}</Alert>}
      <div className="flex gap-2">
        <button type="submit" className="btn-primary" disabled={state === "busy" || !days.length}>Enregistrer</button>
        <button type="button" onClick={() => setOpen(false)} className="btn-ghost">Annuler</button>
      </div>
    </form>
  )
}
