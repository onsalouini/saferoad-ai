import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { Alert, Segmented } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { errorMessage } from "../lib/api"

export default function Auth() {
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [tab, setTab] = useState("login")
  const [form, setForm] = useState({ name: "", email: "", password: "" })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      if (tab === "login") await login(form.email, form.password)
      else await register(form.name, form.email, form.password)
      navigate(location.state?.from || "/trajet")
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-14">
      <div className="card card-pad">
        <h1 className="text-2xl font-bold">{tab === "login" ? "Connexion" : "Créer un compte"}</h1>
        <p className="mt-1 text-sm text-soft">Retrouvez l'historique de vos analyses de trajets.</p>
        <div className="mt-5">
          <Segmented ariaLabel="Type de formulaire" value={tab} onChange={(t) => { setTab(t); setError(null) }}
            options={[{ value: "login", label: "Connexion" }, { value: "register", label: "Inscription" }]} />
        </div>
        <form onSubmit={submit} className="mt-5 space-y-4">
          {tab === "register" && (
            <div>
              <label className="label" htmlFor="name">Nom</label>
              <input id="name" className="field" value={form.name} onChange={set("name")} required minLength={2} autoComplete="name" />
            </div>
          )}
          <div>
            <label className="label" htmlFor="email">E-mail</label>
            <input id="email" type="email" className="field" value={form.email} onChange={set("email")} required autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="password">Mot de passe {tab === "register" && <span className="text-muted">(8 caractères min.)</span>}</label>
            <input id="password" type="password" className="field" value={form.password} onChange={set("password")} required
              minLength={tab === "register" ? 8 : 1} autoComplete={tab === "login" ? "current-password" : "new-password"} />
          </div>
          {error && <Alert tone="error">{error}</Alert>}
          <button className="btn-primary w-full py-3" disabled={busy}>
            {busy ? "Patientez…" : tab === "login" ? "Se connecter" : "Créer mon compte"}
          </button>
        </form>
      </div>
    </div>
  )
}
