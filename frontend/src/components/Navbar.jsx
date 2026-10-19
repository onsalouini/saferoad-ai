import { useState } from "react"
import { Link, NavLink } from "react-router-dom"
import { useAuth } from "../context/AuthContext"

const LINKS = [
  { to: "/trajet", label: "Analyser un trajet" },
  { to: "/simulation", label: "Simulateur" },
  { to: "/modele", label: "Le modèle" },
  { to: "/historique", label: "Historique" },
]

export default function Navbar() {
  const { user, logout } = useAuth()
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

        <div className="hidden md:flex items-center gap-1">
          {LINKS.map((l) => <NavLink key={l.to} to={l.to} className={cls}>{l.label}</NavLink>)}
        </div>

        <div className="hidden md:flex items-center gap-2">
          {user ? (
            <>
              <span className="text-sm text-soft">Bonjour, <b className="text-ink">{user.name}</b></span>
              <button onClick={logout} className="btn-ghost py-1.5">Déconnexion</button>
            </>
          ) : (
            <NavLink to="/connexion" className="btn-primary py-1.5">Connexion</NavLink>
          )}
        </div>

        <button className="md:hidden btn-ghost px-3 py-1.5" onClick={() => setOpen((o) => !o)}
          aria-expanded={open} aria-label="Menu">☰</button>
      </nav>
      {open && (
        <div className="md:hidden border-t border-line/70 px-4 py-3 flex flex-col gap-1">
          {LINKS.map((l) => <NavLink key={l.to} to={l.to} className={cls} onClick={() => setOpen(false)}>{l.label}</NavLink>)}
          {user
            ? <button onClick={() => { logout(); setOpen(false) }} className="btn-ghost mt-2">Déconnexion ({user.name})</button>
            : <NavLink to="/connexion" className="btn-primary mt-2" onClick={() => setOpen(false)}>Connexion</NavLink>}
        </div>
      )}
    </header>
  )
}
