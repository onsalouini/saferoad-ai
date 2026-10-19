import { useEffect, useState } from "react"
import { Link, useLocation } from "react-router-dom"
import DepartureChart from "../components/DepartureChart"
import FactorBars from "../components/FactorBars"
import PlaceSearch from "../components/PlaceSearch"
import RiskGauge from "../components/RiskGauge"
import RouteMap from "../components/RouteMap"
import { Alert, Card, Segmented, Spinner, Stat, StatusBadge, Toggle } from "../components/ui"
import { useAuth } from "../context/AuthContext"
import { api, errorMessage } from "../lib/api"
import { MODES, STATUS, fmt } from "../lib/risk"

const ROAD = [
  ["Junction", "Intersections"], ["Traffic_Signal", "Feux"], ["Crossing", "Passages piétons"],
  ["Stop", "Stops"], ["Roundabout", "Ronds-points"], ["Railway", "Passages à niveau"],
]

const EXAMPLES = [
  { label: "Los Angeles → San Diego", o: { lat: 34.0537, lng: -118.2428, label: "Los Angeles" }, d: { lat: 32.7157, lng: -117.1611, label: "San Diego" } },
  { label: "Dayton → Columbus", o: { lat: 39.7589, lng: -84.1916, label: "Dayton" }, d: { lat: 39.9612, lng: -82.9988, label: "Columbus" } },
  { label: "Miami → Orlando", o: { lat: 25.7617, lng: -80.1918, label: "Miami" }, d: { lat: 28.5384, lng: -81.3789, label: "Orlando" } },
]

// Lien partageable : /trajet?de=lat,lng,Nom&a=lat,lng,Nom&mode=pro
function placeFromParam(v) {
  if (!v) return null
  const [lat, lng, ...name] = v.split(",")
  if (!Number.isFinite(+lat) || !Number.isFinite(+lng)) return null
  return { lat: +lat, lng: +lng, label: name.join(",") || `${(+lat).toFixed(3)}, ${(+lng).toFixed(3)}` }
}

function initialTrip(location) {
  if (location.state?.origin) return location.state
  const q = new URLSearchParams(location.search)
  const origin = placeFromParam(q.get("de"))
  const destination = placeFromParam(q.get("a"))
  return { origin, destination, mode: MODES[q.get("mode")] ? q.get("mode") : undefined }
}

export default function Trip() {
  const { user } = useAuth()
  const location = useLocation()
  const [init] = useState(() => initialTrip(location))
  const [origin, setOrigin] = useState(init.origin || null)
  const [destination, setDestination] = useState(init.destination || null)
  const [mode, setMode] = useState(init.mode || "standard")
  const [road, setRoad] = useState({})
  const [showRoad, setShowRoad] = useState(false)
  const [result, setResult] = useState(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const analyse = async (o = origin, d = destination) => {
    if (!o || !d) return
    setLoading(true); setError(null)
    try {
      const { data } = await api.post("/predict/trip", { origin: o, destination: d, mode, road })
      setResult(data); setSelected(data.recommended_route)
      const enc = (p) => `${p.lat.toFixed(5)},${p.lng.toFixed(5)},${p.label || ""}`
      window.history.replaceState(window.history.state, "",
        `/trajet?de=${encodeURIComponent(enc(o))}&a=${encodeURIComponent(enc(d))}&mode=${mode}`)
    } catch (e) { setError(errorMessage(e)) } finally { setLoading(false) }
  }

  // Relance depuis l'historique
  useEffect(() => {
    const { origin: o, destination: d } = init
    if (!o || !d) return
    const t = setTimeout(() => analyse(o, d))
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const onMapClick = async ({ lat, lng }) => {
    const place = { lat, lng, label: `${lat.toFixed(4)}, ${lng.toFixed(4)}` }
    try {
      const { data } = await api.get("/geo/reverse", { params: { lat, lng } })
      place.label = data.city || data.label.split(",")[0]
    } catch { /* libellé par défaut */ }
    if (!origin) setOrigin(place)
    else setDestination(place)
  }

  const route = result?.routes[selected]
  const swap = () => { setOrigin(destination); setDestination(origin) }

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header>
        <p className="eyebrow">Analyse de trajet</p>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">Quel est le risque de votre trajet ?</h1>
        <p className="mt-2 max-w-3xl text-soft">
          Itinéraire réel, météo prévue à l'heure de passage sur chaque tronçon et prédiction du modèle,
          avec le meilleur horaire de départ sur les 24 prochaines heures.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-12">
        {/* Formulaire */}
        <Card className="lg:col-span-4 h-fit" title="Votre trajet">
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); analyse() }}>
            <PlaceSearch label="Départ" value={origin} onChange={setOrigin} placeholder="Ville, adresse…" allowLocate dotClass="bg-accent" />
            <div className="flex justify-center -my-1">
              <button type="button" onClick={swap} className="text-xs text-muted hover:text-ink" aria-label="Inverser départ et arrivée">⇅ inverser</button>
            </div>
            <PlaceSearch label="Arrivée" value={destination} onChange={setDestination} placeholder="Ville, adresse…" dotClass="bg-ink" />
            <p className="text-xs text-muted">Astuce : cliquez sur la carte pour placer le départ puis l'arrivée.</p>

            <div>
              <span className="label">Mode d'alerte</span>
              <Segmented ariaLabel="Mode d'alerte" value={mode} onChange={setMode}
                options={Object.entries(MODES).map(([value, m]) => ({ value, label: m.label, hint: m.hint }))} />
              <p className="mt-1.5 text-xs text-muted">{MODES[mode].hint}</p>
            </div>

            <div>
              <button type="button" className="text-sm text-soft hover:text-ink" onClick={() => setShowRoad((s) => !s)} aria-expanded={showRoad}>
                {showRoad ? "▾" : "▸"} Caractéristiques de la route (optionnel)
              </button>
              {showRoad && (
                <div className="mt-2 grid grid-cols-2 gap-2">
                  {ROAD.map(([k, l]) => (
                    <Toggle key={k} label={l} checked={!!road[k]} onChange={(v) => setRoad((r) => ({ ...r, [k]: v }))} />
                  ))}
                </div>
              )}
            </div>

            <button type="submit" className="btn-primary w-full py-3" disabled={!origin || !destination || loading}>
              {loading ? "Analyse en cours…" : "Analyser le trajet →"}
            </button>
            {!user && (
              <p className="text-xs text-muted text-center">
                <Link to="/connexion" className="text-accent hover:underline">Connectez-vous</Link> pour enregistrer vos analyses.
              </p>
            )}
          </form>

          {!result && (
            <div className="mt-5 border-t border-line/60 pt-4">
              <p className="eyebrow mb-2">Exemples (zone couverte : USA)</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLES.map((ex) => (
                  <button key={ex.label} className="rounded-full bg-raised px-3 py-1 text-xs text-soft hover:text-ink border border-line/60"
                    onClick={() => { setOrigin(ex.o); setDestination(ex.d) }}>{ex.label}</button>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Carte */}
        <div className="lg:col-span-8 space-y-3">
          <div className="card overflow-hidden p-1.5 relative">
            <RouteMap origin={origin} destination={destination} routes={result?.routes || []}
              selected={selected} onSelect={setSelected} onMapClick={onMapClick} height={500} />
            {loading && (
              <div className="absolute inset-0 z-[1000] grid place-items-center bg-page/60 rounded-2xl">
                <div className="card px-5 py-4"><Spinner label="Calcul de l'itinéraire, de la météo et du risque…" /></div>
              </div>
            )}
          </div>
          {error && <Alert tone="error" title="Analyse impossible">{error}</Alert>}
        </div>
      </div>

      {result && route && <TripResult result={result} route={route} selected={selected} setSelected={setSelected} />}
    </div>
  )
}

function TripResult({ result, route, selected, setSelected }) {
  const s = route.summary
  const best = route.best_departure
  const now = route.departures[0]
  const gain = now.risk_score - best.risk_score
  const worstSeg = route.segments.reduce((a, b) => (b.risk_score > a.risk_score ? b : a))

  return (
    <div className="space-y-6">
      {result.warnings.map((w) => <Alert key={w} tone="warning">{w}</Alert>)}

      {/* Synthèse */}
      <div className="grid gap-6 lg:grid-cols-12">
        <Card className="lg:col-span-4" eyebrow="Résultat du modèle" title="Indice de risque du trajet">
          <RiskGauge score={s.risk_score} threshold={s.threshold_used} label="Moyenne sur l'itinéraire, départ maintenant" />
          <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${s.is_high_risk ? "border-critical/50 bg-critical/10" : "border-good/40 bg-good/10"}`}>
            <p className="font-semibold text-ink">
              {s.is_high_risk ? "⚠ Alerte : seuil du mode " : "✓ Sous le seuil du mode "}
              {MODES[s.mode].label} ({Math.round(s.threshold_used * 100)})
            </p>
            <p className="mt-0.5 text-soft">{s.advice}</p>
          </div>
        </Card>

        <div className="lg:col-span-8 grid gap-6">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <Stat label="Distance" value={fmt.num(route.distance_km, 0)} unit="km" />
            <Stat label="Durée estimée" value={fmt.duration(route.duration_min)} />
            <Stat label="Tronçon le plus risqué" value={fmt.num(worstSeg.risk_score, 0)} unit="/ 100" hint={`au km ${fmt.num(worstSeg.km, 0)}`} />
            <Stat label="Points analysés" value={route.segments.length} hint="météo à l'heure de passage" />
          </div>

          <Card eyebrow="Recommandation" title="Meilleur moment pour partir">
            <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
              <div>
                <div className="text-3xl font-bold tnum">{fmt.dayHour(best.time)}</div>
                <div className="mt-1 flex items-center gap-2 text-sm text-soft">
                  Indice <b className="text-ink tnum">{fmt.num(best.risk_score)}</b> <StatusBadge status={best.status} />
                </div>
              </div>
              <p className="flex-1 min-w-[16rem] text-sm text-soft">
                {gain >= 1
                  ? <>Partir à ce créneau réduit l'indice de <b className="text-ink">{fmt.num(gain)} points</b> par rapport à un départ immédiat ({fmt.num(now.risk_score)}).</>
                  : <>Partir maintenant est déjà le créneau le plus favorable des 24 prochaines heures.</>}
                {" "}Conditions prévues au départ : {best.weather_label.toLowerCase()}.
              </p>
            </div>
          </Card>
        </div>
      </div>

      {/* Comparaison d'itinéraires */}
      {result.routes.length > 1 && (
        <Card eyebrow="Itinéraires" title="Comparaison des itinéraires">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {result.routes.map((r, i) => (
              <button key={i} onClick={() => setSelected(i)}
                className={`text-left rounded-xl border px-4 py-3 transition ${i === selected ? "border-accent bg-accent/10" : "border-line/60 bg-raised/50 hover:border-line"}`}>
                <div className="flex items-center justify-between">
                  <span className="font-semibold">Itinéraire {i + 1}</span>
                  {r.recommended && <span className="rounded-full bg-good/15 px-2 py-0.5 text-xs font-semibold text-good">✓ Le plus sûr</span>}
                </div>
                <div className="mt-1 text-sm text-soft tnum">{fmt.num(r.distance_km, 0)} km · {fmt.duration(r.duration_min)}</div>
                <div className="mt-2 flex items-center gap-2 text-sm">
                  Indice <b className="tnum">{fmt.num(r.summary.risk_score)}</b> <StatusBadge status={r.summary.status} />
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card eyebrow="Prévision 24 h" title="Indice de risque selon l'heure de départ"
        action={<span className="text-xs text-muted hidden sm:block">Survolez une colonne pour le détail</span>}>
        <DepartureChart departures={route.departures} threshold={s.threshold_used} best={best} />
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card eyebrow="Explicabilité" title={`Pourquoi ce score ? (tronçon le plus risqué, km ${fmt.num(route.peak.km, 0)})`}>
          <FactorBars factors={route.explanation.factors} />
        </Card>

        <Card eyebrow="Détail" title="Risque tronçon par tronçon" bodyClass="px-2 pb-4 pt-2 sm:px-3">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted">
                  <th className="px-3 py-2 font-medium">Km</th>
                  <th className="px-3 py-2 font-medium">État</th>
                  <th className="px-3 py-2 font-medium">Météo au passage</th>
                  <th className="px-3 py-2 font-medium text-right">Indice</th>
                  <th className="px-3 py-2 font-medium">Niveau</th>
                </tr>
              </thead>
              <tbody>
                {route.segments.map((seg, i) => (
                  <tr key={i} className="border-t border-line/50">
                    <td className="px-3 py-2 tnum text-soft">{fmt.num(seg.km, 0)}</td>
                    <td className="px-3 py-2">{seg.state || <span className="text-muted">hors USA</span>}</td>
                    <td className="px-3 py-2 text-soft">
                      {seg.weather.weather_label}, {fmt.fToC(seg.weather.Temperature_F)} °C
                      {seg.weather.IsNight && <span className="ml-1 text-muted">· nuit</span>}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold tnum">{fmt.num(seg.risk_score)}</td>
                    <td className="px-3 py-2"><StatusBadge status={seg.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      <p className="text-xs text-muted">
        Lecture : l'indice (0-100) est le score du modèle LightGBM entraîné sur 7,7 M d'accidents américains ; il estime la
        propension d'un accident à être <b>grave</b> dans ces conditions et a tendance à surestimer les valeurs moyennes
        (voir <Link to="/modele" className="text-accent hover:underline">fiabilité du modèle</Link>).
        Niveaux : {Object.values(STATUS).map((x) => x.label).join(" < ")}.
      </p>
    </div>
  )
}
