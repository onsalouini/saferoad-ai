import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import { useNotifications } from "../context/NotificationContext"

const LINKS = [
  { to: "/trajet", label: "Analyser un trajet" },
  { to: "/simulation", label: "Simulateur" },
  { to: "/copilote", label: "Copilote IA" },
  { to: "/modele", label: "Le modèle" },
  { to: "/mes-trajets", label: "Mes trajets" },
  { to: "/historique", label: "Historique" },
]

function initials(name = "") {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?"
}

export default function Navbar() {
  const { user, logout } = useAuth()
  const { unread } = useNotifications()
  const [open, setOpen] = useState(false)
  const cls = ({ isActive }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition ${isActive ? "bg-raised text-ink" : "text-soft hover:text-ink"}`

  return (
    <header className="sticky top-0 z-[1100] border-b border-line/70 bg-page/90 backdrop-blur">
      <nav className="mx-auto flex max-w-page items-center justify-between gap-4 px-4 py-3">
        <Link to="/" className="flex items-center gap-2.5" onClick={() => setOpen(false)}>
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent-strong text-white" aria-hidden>
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3l7 3v5c0 4.5-3 8.4-7 10-4-1.6-7-5.5-7-10V6l7-3z" /><path d="M12 8v8M9.5 13h5" />
            </svg>
          </span>
          <span className="text-base font-bold tracking-tight">SafeRoad <span className="text-accent">AI</span></span>
        </Link>

        <div className="hidden lg:flex items-center gap-1">
          {LINKS.map((l) => <NavLink key={l.to} to={l.to} className={cls}>{l.label}</NavLink>)}
        </div>

        <div className="hidden lg:flex items-center gap-2">
          {user ? (
            <>
              <Link to="/mes-trajets" className="relative grid h-9 w-9 place-items-center rounded-lg text-soft hover:bg-raised hover:text-ink"
                aria-label={unread ? `${unread} notification(s) non lue(s)` : "Notifications"}>
                <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
                  <path d="M6 8a6 6 0 1112 0c0 7 3 8 3 8H3s3-1 3-8M10 20a2 2 0 004 0" />
                </svg>
                {unread > 0 && <span className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-critical px-1 text-[10px] font-bold text-white">{unread}</span>}
              </Link>
              <Link to="/compte" className="flex items-center gap-2 text-sm text-soft hover:text-ink" title={`${user.email} · mon compte`}>
                <span className="grid h-8 w-8 place-items-center rounded-full bg-accent/20 text-xs font-bold text-accent" aria-hidden>{initials(user.name)}</span>
                <b className="text-ink max-w-[9rem] truncate">{user.name}</b>
              </Link>
              <button onClick={logout} className="btn-ghost py-1.5">Déconnexion</button>
            </>
          ) : (
            <>
              <NavLink to="/connexion" className="btn-ghost py-1.5">Connexion</NavLink>
              <NavLink to="/inscription" className="btn-primary py-1.5">Créer un compte</NavLink>
            </>
          )}
        </div>

        <button className="lg:hidden btn-ghost px-3 py-1.5" onClick={() => setOpen((o) => !o)}
          aria-expanded={open} aria-label="Menu">☰</button>
      </nav>
      {open && (
        <div className="lg:hidden border-t border-line/70 px-4 py-3 flex flex-col gap-1">
          {LINKS.map((l) => <NavLink key={l.to} to={l.to} className={cls} onClick={() => setOpen(false)}>{l.label}</NavLink>)}
          {user
            ? <button onClick={() => { logout(); setOpen(false) }} className="btn-ghost mt-2">Déconnexion ({user.name})</button>
            : <div className="mt-2 grid grid-cols-2 gap-2">
                <NavLink to="/connexion" className="btn-ghost" onClick={() => setOpen(false)}>Connexion</NavLink>
                <NavLink to="/inscription" className="btn-primary" onClick={() => setOpen(false)}>Créer un compte</NavLink>
              </div>}
        </div>
      )}
    </header>
  )
}
