import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Alert, Card, Spinner, StatusBadge } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { api, errorMessage } from "../lib/api"
import { MODES, fmt } from "../lib/risk"

export default function History() {
  const { user, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!user) return
    api.get("/history").then((r) => setItems(r.data)).catch((e) => setError(errorMessage(e)))
  }, [user])

  const remove = async (id) => {
    await api.delete(`/history/${id}`)
    setItems((xs) => xs.filter((x) => x.id !== id))
  }
  const clear = async () => {
    if (!window.confirm("Supprimer tout l'historique ?")) return
    await api.delete("/history")
    setItems([])
  }

  if (authLoading) return <div className="mx-auto max-w-page px-4 py-8"><Spinner /></div>
  if (!user) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold">Historique</h1>
        <p className="mt-2 text-soft">Connectez-vous pour enregistrer et retrouver vos analyses.</p>
        <Link to="/connexion" state={{ from: "/historique" }} className="btn-primary mt-6">Se connecter</Link>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Historique</p>
          <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">Vos analyses</h1>
        </div>
        {items?.length > 0 && <button className="btn-ghost" onClick={clear}>Tout supprimer</button>}
      </header>

      {error && <Alert tone="error">{error}</Alert>}
      {!items && !error && <Spinner />}
      {items?.length === 0 && (
        <Card><p className="text-soft">Aucune analyse pour l'instant. <Link to="/trajet" className="text-accent hover:underline">Analysez votre premier trajet →</Link></p></Card>
      )}

      <ul className="grid gap-3">
        {items?.map((it) => (
          <li key={it.id} className="card px-5 py-4 flex flex-wrap items-center gap-x-6 gap-y-3">
            <div className="min-w-[14rem] flex-1">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-raised px-2 py-0.5 text-xs text-soft capitalize">{it.kind}</span>
                <span className="font-semibold">{it.title}</span>
              </div>
              <div className="mt-1 text-xs text-muted">
                {fmt.date(it.created_at)} · mode {MODES[it.mode]?.label}
                {it.distance_km != null && <> · {fmt.num(it.distance_km, 0)} km · {fmt.duration(it.duration_min)}</>}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold tnum">{Math.round(it.risk_score)}</span>
              <StatusBadge status={it.status} />
            </div>
            {it.best_departure && (
              <div className="text-sm text-soft">Meilleur départ : <b className="text-ink">{fmt.dayHour(it.best_departure.time)}</b></div>
            )}
            <div className="flex gap-2">
              {it.kind === "trajet" && it.origin && (
                <button className="btn-ghost py-1.5" onClick={() => navigate("/trajet", { state: { origin: it.origin, destination: it.destination, mode: it.mode } })}>
                  Relancer
                </button>
              )}
              <button className="btn-ghost py-1.5" onClick={() => remove(it.id)} aria-label={`Supprimer ${it.title}`}>Supprimer</button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
