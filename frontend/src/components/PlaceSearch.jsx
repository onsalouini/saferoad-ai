import { useEffect, useId, useRef, useState } from "react"
import { api } from "../lib/api"

/** Champ de recherche d'adresse avec suggestions (Nominatim via l'API) et géolocalisation. */
export default function PlaceSearch({ label, value, onChange, placeholder, allowLocate = false, dotClass }) {
  const id = useId()
  const [query, setQuery] = useState(value?.label || "")
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const [busy, setBusy] = useState(false)
  const [shown, setShown] = useState(value)
  const timer = useRef()

  // Valeur choisie de l'extérieur (carte, exemple, inversion) -> on met à jour le texte
  if (value !== shown) {
    setShown(value)
    setQuery(value?.label || "")
  }

  useEffect(() => () => clearTimeout(timer.current), [])

  const onType = (text) => {
    setQuery(text)
    clearTimeout(timer.current)
    if (text.trim().length < 3) { setResults([]); return }
    timer.current = setTimeout(async () => {
      setBusy(true)
      try {
        const { data } = await api.get("/geo/search", { params: { q: text } })
        setResults(data); setOpen(true); setActive(-1)
      } catch { setResults([]) } finally { setBusy(false) }
    }, 450)
  }

  const pick = (r) => {
    onChange({ lat: r.lat, lng: r.lng, label: r.name || r.label, full: r.label })
    setOpen(false)
  }

  const locate = () => {
    if (!navigator.geolocation) return
    setBusy(true)
    navigator.geolocation.getCurrentPosition(async (pos) => {
      const { latitude: lat, longitude: lng } = pos.coords
      try {
        const { data } = await api.get("/geo/reverse", { params: { lat, lng } })
        onChange({ lat, lng, label: data.city || data.label, full: data.label })
      } catch {
        onChange({ lat, lng, label: `${lat.toFixed(4)}, ${lng.toFixed(4)}` })
      } finally { setBusy(false) }
    }, () => setBusy(false), { enableHighAccuracy: true, timeout: 10000 })
  }

  const onKey = (e) => {
    if (!open || !results.length) return
    if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, results.length - 1)) }
    if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)) }
    if (e.key === "Enter" && active >= 0) { e.preventDefault(); pick(results[active]) }
    if (e.key === "Escape") setOpen(false)
  }

  return (
    <div className="relative">
      <label htmlFor={id} className="label flex items-center gap-2">
        {dotClass && <span className={`h-2.5 w-2.5 rounded-full ${dotClass}`} />}{label}
      </label>
      <div className="flex gap-2">
        <input id={id} className="field" value={query} placeholder={placeholder} autoComplete="off"
          role="combobox" aria-expanded={open} aria-controls={`${id}-list`}
          onChange={(e) => onType(e.target.value)} onKeyDown={onKey}
          onFocus={() => results.length && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)} />
        {allowLocate && (
          <button type="button" onClick={locate} className="btn-ghost px-3" title="Utiliser ma position" aria-label="Utiliser ma position">
            ◎
          </button>
        )}
      </div>
      {busy && <span className="absolute right-14 top-8 h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />}
      {open && results.length > 0 && (
        <ul id={`${id}-list`} role="listbox"
          className="absolute z-[1000] mt-1 max-h-72 w-full overflow-auto rounded-xl border border-line bg-raised py-1 shadow-xl">
          {results.map((r, i) => (
            <li key={`${r.lat},${r.lng},${i}`} role="option" aria-selected={i === active}
              onMouseDown={() => pick(r)}
              className={`cursor-pointer px-3 py-2 text-sm ${i === active ? "bg-line" : "hover:bg-line/60"}`}>
              <div className="font-medium text-ink">{r.name}</div>
              <div className="truncate text-xs text-muted">{r.label}</div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
