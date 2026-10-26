import { useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"
import { CopilotIcon } from "../components/Assistant"
import { Alert } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { errorMessage } from "../lib/api"

const BENEFITS = [
  ["Historique de vos analyses", "Retrouvez et relancez vos trajets en un clic."],
  ["Copilote IA", "Briefings de trajet et réponses à vos questions de conduite."],
  ["Gratuit", "Aucune carte bancaire, vos données restent les vôtres."],
]

const STRENGTH = [
  { label: "Trop court", cls: "bg-critical", w: "w-1/5" },
  { label: "Faible", cls: "bg-serious", w: "w-2/5" },
  { label: "Moyen", cls: "bg-warning", w: "w-3/5" },
  { label: "Bon", cls: "bg-good", w: "w-4/5" },
  { label: "Excellent", cls: "bg-good", w: "w-full" },
]

function strengthOf(pw) {
  if (pw.length < 8) return 0
  let score = 1
  if (pw.length >= 12) score++
  if (/[a-z]/.test(pw) && /[A-Z]/.test(pw)) score++
  if (/\d/.test(pw) && /[^A-Za-z0-9]/.test(pw)) score++
  return Math.min(score, 4)
}

function PasswordField({ id, label, value, onChange, autoComplete, minLength, hint }) {
  const [show, setShow] = useState(false)
  return (
    <div>
      <label className="label" htmlFor={id}>{label} {hint && <span className="text-muted">{hint}</span>}</label>
      <div className="relative">
        <input id={id} type={show ? "text" : "password"} className="field pr-20" value={value} onChange={onChange}
          required minLength={minLength} maxLength={72} autoComplete={autoComplete} />
        <button type="button" onClick={() => setShow((s) => !s)}
          className="absolute inset-y-0 right-0 px-3 text-xs font-medium text-soft hover:text-ink"
          aria-label={show ? "Masquer le mot de passe" : "Afficher le mot de passe"}>
          {show ? "Masquer" : "Afficher"}
        </button>
      </div>
    </div>
  )
}

export default function Auth() {
  const { user, login, register, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [form, setForm] = useState({ name: "", email: "", password: "", confirm: "", phone: "", location: "" })
  const [showMore, setShowMore] = useState(false)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const tab = location.pathname === "/inscription" ? "register" : "login"
  const isRegister = tab === "register"
  const strength = strengthOf(form.password)

  const switchTab = (t) => {
    setError(null)
    navigate(t === "login" ? "/connexion" : "/inscription", { replace: true, state: location.state })
  }

  const submit = async (e) => {
    e.preventDefault()
    if (isRegister && form.password !== form.confirm) { setError("Les deux mots de passe ne correspondent pas."); return }
    setBusy(true); setError(null)
    try {
      if (isRegister) {
        await register(form.name, form.email, form.password, { phone: form.phone || null, location: form.location || null })
      } else {
        await login(form.email, form.password)
      }
      navigate(location.state?.from || "/trajet")
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }

  if (user) {
    return (
      <div className="mx-auto max-w-md px-4 py-20 text-center">
        <div className="card card-pad">
          <p className="text-lg font-semibold">Vous êtes connecté en tant que {user.name}</p>
          <p className="mt-1 text-sm text-soft">{user.email}</p>
          <div className="mt-6 flex justify-center gap-2">
            <Link to="/trajet" className="btn-primary">Analyser un trajet</Link>
            <button onClick={logout} className="btn-ghost">Se déconnecter</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mx-auto grid max-w-page gap-10 px-4 py-12 lg:grid-cols-2 lg:items-center lg:py-20">
      {/* Panneau d'accroche */}
      <div className="hidden lg:block">
        <p className="eyebrow text-accent">SafeRoad AI</p>
        <h1 className="mt-3 text-4xl font-bold leading-tight tracking-tight">
          {isRegister ? "Rejoignez SafeRoad et roulez plus sereinement." : "Content de vous revoir."}
        </h1>
        <p className="mt-4 max-w-md text-soft">
          {isRegister
            ? "Un compte gratuit débloque l'historique de vos analyses et le copilote IA."
            : "Connectez-vous pour retrouver vos trajets et discuter avec le copilote IA."}
        </p>
        <ul className="mt-8 space-y-4">
          {BENEFITS.map(([t, d], i) => (
            <li key={t} className="flex gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-accent/15 text-accent">
                {i === 1 ? <CopilotIcon className="h-4 w-4" /> : <span className="text-sm font-bold">✓</span>}
              </span>
              <div>
                <p className="font-semibold">{t}</p>
                <p className="text-sm text-soft">{d}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {/* Formulaire */}
      <div className="mx-auto w-full max-w-md">
        <div className="card card-pad sm:p-8">
          <div className="grid grid-cols-2 rounded-xl border border-line/60 bg-raised p-1" role="tablist" aria-label="Connexion ou inscription">
            {[["login", "Connexion"], ["register", "Inscription"]].map(([v, l]) => (
              <button key={v} type="button" role="tab" aria-selected={tab === v} onClick={() => switchTab(v)}
                className={`rounded-lg py-2 text-sm font-semibold transition ${tab === v ? "bg-accent-strong text-white" : "text-soft hover:text-ink"}`}>
                {l}
              </button>
            ))}
          </div>

          <h2 className="mt-6 text-2xl font-bold">{isRegister ? "Créer un compte" : "Se connecter"}</h2>
          <p className="mt-1 text-sm text-soft">
            {isRegister ? "Déjà inscrit ? " : "Pas encore de compte ? "}
            <button type="button" onClick={() => switchTab(isRegister ? "login" : "register")} className="font-medium text-accent hover:underline">
              {isRegister ? "Se connecter" : "Créer un compte gratuit"}
            </button>
          </p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            {isRegister && (
              <div>
                <label className="label" htmlFor="name">Nom complet</label>
                <input id="name" className="field" value={form.name} onChange={set("name")} required minLength={2} maxLength={60} autoComplete="name" />
              </div>
            )}
            <div>
              <label className="label" htmlFor="email">E-mail</label>
              <input id="email" type="email" className="field" value={form.email} onChange={set("email")} required autoComplete="email" placeholder="vous@exemple.com" />
            </div>
            <PasswordField id="password" label="Mot de passe" value={form.password} onChange={set("password")}
              hint={isRegister ? "(8 caractères min.)" : null} minLength={isRegister ? 8 : 1}
              autoComplete={isRegister ? "new-password" : "current-password"} />
            {!isRegister && (
              <p className="-mt-2 text-right text-xs">
                <Link to="/mot-de-passe-oublie" className="text-soft hover:text-accent">Mot de passe oublié ?</Link>
              </p>
            )}

            {isRegister && form.password && (
              <div aria-live="polite">
                <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                  <div className={`h-full rounded-full transition-all ${STRENGTH[strength].cls} ${STRENGTH[strength].w}`} />
                </div>
                <p className="mt-1 text-xs text-muted">Robustesse : {STRENGTH[strength].label}</p>
              </div>
            )}

            {isRegister && (
              <PasswordField id="confirm" label="Confirmer le mot de passe" value={form.confirm} onChange={set("confirm")}
                minLength={8} autoComplete="new-password" />
            )}

            {isRegister && (
              <div>
                <button type="button" onClick={() => setShowMore((s) => !s)} aria-expanded={showMore}
                  className="text-xs font-medium text-soft hover:text-ink">
                  {showMore ? "−" : "+"} Informations facultatives (téléphone, ville)
                </button>
                {showMore && (
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div>
                      <label className="label" htmlFor="phone">Téléphone</label>
                      <input id="phone" type="tel" className="field" value={form.phone} onChange={set("phone")} maxLength={30} autoComplete="tel" />
                    </div>
                    <div>
                      <label className="label" htmlFor="location">Ville</label>
                      <input id="location" className="field" value={form.location} onChange={set("location")} maxLength={120} placeholder="Tunis, Tunisie" />
                    </div>
                  </div>
                )}
              </div>
            )}

            {error && <Alert tone="error">{error}</Alert>}
            <button className="btn-primary w-full py-3" disabled={busy}>
              {busy ? "Patientez…" : isRegister ? "Créer mon compte" : "Se connecter"}
            </button>
          </form>

          {isRegister && (
            <p className="mt-4 text-center text-xs text-muted">
              Votre mot de passe est chiffré (bcrypt). SafeRoad est un outil d'aide à la décision, il ne remplace pas la vigilance du conducteur.
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
