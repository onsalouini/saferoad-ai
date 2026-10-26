import { PROFILES } from "../lib/risk"

/** Choix du profil conducteur / véhicule (règles de prudence, n'affecte pas le score du modèle). */
export default function ProfilePicker({ value, onChange, id = "profile" }) {
  return (
    <div>
      <label className="label" htmlFor={id}>Conducteur / véhicule</label>
      <select id={id} className="field" value={value} onChange={(e) => onChange(e.target.value)}>
        {Object.entries(PROFILES).map(([k, p]) => <option key={k} value={k}>{p.icon} {p.label}</option>)}
      </select>
      <p className="mt-1.5 text-xs text-muted">{PROFILES[value].hint}</p>
    </div>
  )
}
