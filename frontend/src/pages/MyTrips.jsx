import { useCallback, useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Alert, Card, Spinner, StatusBadge } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { useNotifications } from "../context/NotificationContext"
import { api, errorMessage } from "../lib/api"
import { DAYS_FR, MODES, fmt } from "../lib/risk"

function daysLabel(days) {
  if (days.length === 7) return "tous les jours"
  if (days.join() === "0,1,2,3,4") return "du lundi au vendredi"
  if (days.join() === "5,6") return "le week-end"
  return days.map((d) => DAYS_FR[d].slice(0, 3).toLowerCase()).join(", ")
}

export default function MyTrips() {
  const { user, loading: authLoading } = useAuth()
  const { items: notifications, refresh, markAllRead, permission, askPermission } = useNotifications()
  const navigate = useNavigate()
  const [trips, setTrips] = useState(null)
  const [config, setConfig] = useState(null)
  const [error, setError] = useState(null)
  const [checking, setChecking] = useState(null)

  const load = useCallback(() => {
    api.get("/trips").then((r) => setTrips(r.data)).catch((e) => setError(errorMessage(e)))
  }, [])

  useEffect(() => {
    if (!user) return
    load()
    api.get("/alerts/config").then((r) => setConfig(r.data)).catch(() => {})
  }, [user, load])

  const remove = async (id) => {
    if (!window.confirm("Supprimer ce trajet et ses alertes ?")) return
    await api.delete(`/trips/${id}`)
    setTrips((xs) => xs.filter((x) => x.id !== id))
  }

  const checkNow = async (id) => {
    setChecking(id); setError(null)
    try { await api.post(`/trips/${id}/check`); await refresh() } catch (e) { setError(errorMessage(e)) } finally { setChecking(null) }
  }

  if (authLoading) return <div className="mx-auto max-w-page px-4 py-8"><Spinner /></div>
  if (!user) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold">Mes trajets</h1>
        <p className="mt-2 text-soft">Connectez-vous pour enregistrer vos trajets réguliers et recevoir une alerte avant chaque départ.</p>
        <Link to="/connexion" state={{ from: "/mes-trajets" }} className="btn-primary mt-6">Se connecter</Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Alertes de départ</p>
          <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">Mes trajets</h1>
          <p className="mt-2 max-w-2xl text-soft">
            Chaque trajet enregistré est analysé automatiquement dans l'heure qui précède votre départ
            {config?.lead_minutes ? ` (${config.lead_minutes} min avant)` : ""}. Vous recevez une notification, et un e-mail
            si le risque dépasse le seuil ou si une alerte météo officielle est en cours.
          </p>
        </div>
        <Link to="/trajet" className="btn-primary">+ Ajouter depuis une analyse</Link>
      </header>

      {config && !config.email_enabled && (
        <Alert tone="info">Envoi d'e-mails non configuré sur le serveur (SMTP) : les alertes s'affichent uniquement dans l'application.</Alert>
      )}
      {permission === "default" && (
        <Alert tone="info" title="Notifications du navigateur">
          Autorisez les notifications pour être prévenu même quand l'onglet est en arrière-plan.{" "}
          <button type="button" onClick={askPermission} className="font-medium text-accent hover:underline">Autoriser</button>
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}

      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-7" title="Trajets enregistrés">
          {!trips && <Spinner />}
          {trips?.length === 0 && (
            <p className="text-sm text-soft">Aucun trajet. Analysez un trajet puis cliquez sur « Recevoir des alertes pour ce trajet ».</p>
          )}
          <ul className="space-y-3">
            {trips?.map((t) => (
              <li key={t.id} className="rounded-xl border border-line/60 bg-raised/50 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold">{t.label || `${t.origin.label} → ${t.destination.label}`}</p>
                  <span className="text-xs text-muted">mode {MODES[t.mode]?.label}{t.notify_email ? " · e-mail" : ""}</span>
                </div>
                <p className="mt-1 text-sm text-soft">Départ à <b className="text-ink">{t.departure_time}</b>, {daysLabel(t.days)} ({t.tz})</p>
                {t.last_alert_date && <p className="text-xs text-muted">Dernière alerte : {t.last_alert_date}</p>}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className="btn-ghost py-1.5" disabled={checking === t.id} onClick={() => checkNow(t.id)}>
                    {checking === t.id ? "Analyse…" : "Vérifier maintenant"}
                  </button>
                  <button type="button" className="btn-ghost py-1.5"
                    onClick={() => navigate("/trajet", { state: { origin: t.origin, destination: t.destination, mode: t.mode } })}>Ouvrir l'analyse</button>
                  <button type="button" className="btn-ghost py-1.5" onClick={() => remove(t.id)}>Supprimer</button>
                </div>
              </li>
            ))}
          </ul>
        </Card>

        <Card className="lg:col-span-5" title="Notifications"
          action={notifications.some((n) => !n.read) && <button type="button" className="text-xs text-accent hover:underline" onClick={markAllRead}>Tout marquer comme lu</button>}>
          {notifications.length === 0 && <p className="text-sm text-soft">Aucune notification pour l'instant.</p>}
          <ul className="space-y-3">
            {notifications.map((n) => (
              <li key={n.id} className={`rounded-xl border px-4 py-3 text-sm ${n.read ? "border-line/50" : "border-accent/50 bg-accent/5"}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="font-semibold text-ink">{n.title}</p>
                  <StatusBadge status={n.status} />
                </div>
                <p className="mt-1 text-soft">{n.message}</p>
                <p className="mt-1 text-xs text-muted">{fmt.date(n.created_at)}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  )
}
