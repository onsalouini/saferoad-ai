import { useEffect, useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Alert, Card, Spinner, Stat } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { API_URL, api, errorMessage } from "../lib/api"
import { disablePush, enablePush, pushStatus, pushSupported } from "../lib/push"
import { fmt } from "../lib/risk"

/** Lien reçu par e-mail : /verifier-email?token=… */
export function VerifyEmail() {
  const [params] = useSearchParams()
  const [state, setState] = useState({ busy: true })

  useEffect(() => {
    api.post("/auth/verify", { token: params.get("token") || "" })
      .then((r) => setState({ ok: r.data.message }))
      .catch((e) => setState({ error: errorMessage(e) }))
  }, [params])

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <div className="card card-pad text-center">
        <h1 className="text-2xl font-bold">Confirmation de l'adresse e-mail</h1>
        <div className="mt-6">
          {state.busy && <Spinner />}
          {state.ok && <Alert tone="info" title="C'est fait">{state.ok} Vous recevrez désormais les alertes par e-mail.</Alert>}
          {state.error && <Alert tone="error">{state.error}</Alert>}
        </div>
        <Link to="/mes-trajets" className="btn-primary mt-6">Mes trajets</Link>
      </div>
    </div>
  )
}

export default function Account() {
  const { user, loading, logout } = useAuth()
  const navigate = useNavigate()
  const [push, setPush] = useState(null)
  const [usage, setUsage] = useState(null)
  const [msg, setMsg] = useState(null)
  const [password, setPassword] = useState("")
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!user) return
    pushStatus().then(setPush).catch(() => setPush("unsupported"))
    api.get("/assistant/usage").then((r) => setUsage(r.data)).catch(() => {})
  }, [user])

  if (loading) return <div className="mx-auto max-w-page px-4 py-8"><Spinner /></div>
  if (!user) {
    return (
      <div className="mx-auto max-w-xl px-4 py-16 text-center">
        <h1 className="text-2xl font-bold">Mon compte</h1>
        <Link to="/connexion" state={{ from: "/compte" }} className="btn-primary mt-6">Se connecter</Link>
      </div>
    )
  }

  const run = async (fn, ok) => {
    setMsg(null)
    try { await fn(); setMsg({ tone: "info", text: ok }) } catch (e) { setMsg({ tone: "error", text: e.response ? errorMessage(e) : e.message }) }
  }
  const togglePush = () => run(async () => {
    if (push === "subscribed") { await disablePush(); setPush("off") } else { await enablePush(); setPush("subscribed") }
  }, push === "subscribed" ? "Notifications désactivées sur cet appareil." : "Notifications activées sur cet appareil.")
  const remove = () => run(async () => {
    await api.post("/account/delete", { password })
    await logout()
    navigate("/")
  }, "Compte supprimé.")
  const months = Object.entries(usage?.by_month || {}).sort().reverse()

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header>
        <p className="eyebrow">Compte</p>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">{user.name}</h1>
        <p className="mt-1 text-soft">{user.email} · inscrit le {fmt.date(user.created_at)}</p>
      </header>
      {msg && <Alert tone={msg.tone}>{msg.text}</Alert>}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Adresse e-mail">
          {user.email_verified
            ? <p className="text-sm text-good">✓ Adresse confirmée : vous recevez les alertes par e-mail.</p>
            : (
              <div className="space-y-3 text-sm text-soft">
                <p>Adresse non confirmée : les alertes ne sont pas envoyées par e-mail tant qu'elle n'est pas vérifiée.</p>
                <button type="button" className="btn-ghost" onClick={() => run(() => api.post("/auth/verify/send"), "E-mail de confirmation envoyé.")}>
                  Renvoyer l'e-mail de confirmation
                </button>
              </div>
            )}
        </Card>

        <Card title="Notifications sur cet appareil">
          {!pushSupported || push === "unsupported"
            ? <p className="text-sm text-soft">Ce navigateur ne gère pas les notifications push (sur iPhone : installez d'abord l'application sur l'écran d'accueil).</p>
            : push === "denied"
              ? <p className="text-sm text-soft">Notifications bloquées dans les réglages du navigateur pour ce site.</p>
              : (
                <div className="space-y-3 text-sm text-soft">
                  <p>Recevez les alertes de départ même quand SafeRoad est fermé.</p>
                  <div className="flex flex-wrap gap-2">
                    <button type="button" className={push === "subscribed" ? "btn-ghost" : "btn-primary"} onClick={togglePush} disabled={push === null}>
                      {push === "subscribed" ? "Désactiver" : "Activer les notifications"}
                    </button>
                    {push === "subscribed" && (
                      <button type="button" className="btn-ghost" onClick={() => run(() => api.post("/push/test"), "Notification de test envoyée.")}>Tester</button>
                    )}
                  </div>
                </div>
              )}
        </Card>

        <Card title="Copilote IA : consommation">
          {!usage && <p className="text-sm text-soft">Aucune donnée.</p>}
          {usage && (
            <>
              <p className="text-sm text-soft">Limite : {usage.limit_per_hour} messages par heure.</p>
              {months.length === 0 && <p className="mt-2 text-sm text-muted">Vous n'avez pas encore utilisé le copilote.</p>}
              {months.length > 0 && (
                <div className="mt-3 grid grid-cols-3 gap-3">
                  <Stat label={`Requêtes (${months[0][0]})`} value={fmt.int(months[0][1].requests || 0)} />
                  <Stat label="Jetons lus" value={fmt.int(months[0][1].input_tokens || 0)} />
                  <Stat label="Jetons écrits" value={fmt.int(months[0][1].output_tokens || 0)} />
                </div>
              )}
            </>
          )}
        </Card>

        <Card title="Mes données (RGPD)">
          <div className="space-y-4 text-sm text-soft">
            <p>Téléchargez toutes vos données (profil, historique, trajets, notifications) au format JSON.</p>
            <a href={`${API_URL}/account/export`} className="btn-ghost">Exporter mes données</a>
            <div className="border-t border-line/60 pt-4">
              {!confirmDelete
                ? <button type="button" className="text-critical hover:underline" onClick={() => setConfirmDelete(true)}>Supprimer mon compte…</button>
                : (
                  <form onSubmit={(e) => { e.preventDefault(); remove() }} className="space-y-3">
                    <p className="text-ink">Suppression définitive : historique, trajets et notifications seront effacés. Vos signalements publics restent, anonymisés.</p>
                    <label className="label" htmlFor="del-pw">Mot de passe</label>
                    <input id="del-pw" type="password" className="field" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
                    <div className="flex gap-2">
                      <button type="submit" className="btn bg-critical text-white hover:opacity-90">Supprimer définitivement</button>
                      <button type="button" className="btn-ghost" onClick={() => setConfirmDelete(false)}>Annuler</button>
                    </div>
                  </form>
                )}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
