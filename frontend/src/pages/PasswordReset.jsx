import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { Alert } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { api, errorMessage } from "../lib/api"

function Shell({ title, subtitle, children }) {
  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <div className="card card-pad sm:p-8">
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 text-sm text-soft">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>
    </div>
  )
}

/** Étape 1 : demande d'un lien de réinitialisation par e-mail. */
export function ForgotPassword() {
  const [email, setEmail] = useState("")
  const [state, setState] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setState({ busy: true })
    try {
      const { data } = await api.post("/auth/forgot", { email })
      setState({ done: data.message })
    } catch (err) { setState({ error: errorMessage(err) }) }
  }

  return (
    <Shell title="Mot de passe oublié" subtitle="Saisissez votre e-mail : nous vous envoyons un lien valable 30 minutes.">
      {state?.done ? (
        <Alert tone="info" title="Demande envoyée">{state.done}</Alert>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label" htmlFor="email">E-mail</label>
            <input id="email" type="email" className="field" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          {state?.error && <Alert tone="error">{state.error}</Alert>}
          <button type="submit" className="btn-primary w-full py-3" disabled={state?.busy}>{state?.busy ? "Envoi…" : "Envoyer le lien"}</button>
        </form>
      )}
      <p className="mt-6 text-center text-sm"><Link to="/connexion" className="text-accent hover:underline">← Retour à la connexion</Link></p>
    </Shell>
  )
}

/** Étape 2 : choix du nouveau mot de passe depuis le lien reçu. */
export function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get("token") || ""
  const { resetPassword } = useAuth()
  const navigate = useNavigate()
  const [pw, setPw] = useState("")
  const [confirm, setConfirm] = useState("")
  const [state, setState] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    if (pw !== confirm) { setState({ error: "Les deux mots de passe ne correspondent pas." }); return }
    setState({ busy: true })
    try {
      await resetPassword(token, pw)
      navigate("/trajet")
    } catch (err) { setState({ error: errorMessage(err) }) }
  }

  if (!token) {
    return (
      <Shell title="Lien incomplet" subtitle="Ce lien de réinitialisation ne contient pas de jeton.">
        <Link to="/mot-de-passe-oublie" className="btn-primary w-full">Refaire une demande</Link>
      </Shell>
    )
  }

  return (
    <Shell title="Nouveau mot de passe" subtitle="Les autres sessions ouvertes seront déconnectées.">
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="label" htmlFor="pw">Nouveau mot de passe <span className="text-muted">(8 caractères min.)</span></label>
          <input id="pw" type="password" className="field" value={pw} onChange={(e) => setPw(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" />
        </div>
        <div>
          <label className="label" htmlFor="pw2">Confirmer</label>
          <input id="pw2" type="password" className="field" value={confirm} onChange={(e) => setConfirm(e.target.value)} required minLength={8} maxLength={72} autoComplete="new-password" />
        </div>
        {state?.error && <Alert tone="error">{state.error}</Alert>}
        <button type="submit" className="btn-primary w-full py-3" disabled={state?.busy}>{state?.busy ? "Patientez…" : "Changer le mot de passe"}</button>
      </form>
    </Shell>
  )
}
