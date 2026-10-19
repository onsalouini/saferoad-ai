import { useState } from "react"
import FactorBars from "../components/FactorBars"
import PlaceSearch from "../components/PlaceSearch"
import RiskGauge from "../components/RiskGauge"
import { Alert, Card, Segmented, Spinner, Toggle } from "../components/ui"
import { api, errorMessage } from "../lib/api"
import { MODES, WEATHER_FR, fmt } from "../lib/risk"

const ROAD = [
  ["Junction", "Intersection"], ["Traffic_Signal", "Feu de signalisation"], ["Crossing", "Passage piéton"],
  ["Stop", "Panneau stop"], ["Roundabout", "Rond-point"], ["Give_Way", "Cédez-le-passage"],
  ["Railway", "Passage à niveau"], ["Bump", "Ralentisseur"], ["Amenity", "Commerces / services"],
  ["Station", "Station"],
]

const pad = (n) => String(n).padStart(2, "0")
const localNow = () => {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`
}

// Saisie en unités métriques, conversion vers les unités du modèle (US) à l'envoi
const INITIAL = {
  place: { lat: 39.7589, lng: -84.1916, label: "Dayton, Ohio" },
  when: localNow(),
  tempC: 13, humidity: 60, pressureHpa: 1013, visibilityKm: 16, windKmh: 10, precipMm: 0,
  weather: "Fair", night: false, mode: "standard", road: {},
}

function NumField({ k, label, unit, value, onChange, step = 1, min, max }) {
  return (
    <div>
      <label className="label" htmlFor={k}>{label} <span className="text-muted">({unit})</span></label>
      <input id={k} type="number" className="field tnum" value={value} step={step} min={min} max={max} onChange={onChange} required />
    </div>
  )
}

export default function Simulator() {
  const [f, setF] = useState(INITIAL)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [error, setError] = useState(null)
  const [weatherNote, setWeatherNote] = useState(null)
  const set = (k) => (v) => setF((p) => ({ ...p, [k]: v }))
  const num = (k) => (e) => set(k)(e.target.value === "" ? "" : Number(e.target.value))

  const fillWeather = async () => {
    setFetching(true); setError(null)
    try {
      const { data: w } = await api.get("/weather", { params: { lat: f.place.lat, lng: f.place.lng } })
      setF((p) => ({
        ...p, tempC: fmt.fToC(w.Temperature_F), humidity: Math.round(w.Humidity),
        pressureHpa: Math.round(w.Pressure / 0.02953), visibilityKm: fmt.miToKm(w.Visibility_mi),
        windKmh: fmt.mphToKmh(w.Wind_Speed_mph), precipMm: fmt.inToMm(w.Precipitation_in),
        weather: w.Weather_Condition, night: w.IsNight, when: w.time,
      }))
      setWeatherNote(`Météo réelle chargée : ${w.weather_label.toLowerCase()} (Open-Meteo, ${fmt.date(w.time)} heure locale).`)
    } catch (e) { setError(errorMessage(e)) } finally { setFetching(false) }
  }

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true); setError(null)
    const d = new Date(f.when)
    try {
      const { data } = await api.post("/predict", {
        Start_Lat: f.place.lat, Start_Lng: f.place.lng, City: f.place.label,
        Temperature_F: (Number(f.tempC) * 9) / 5 + 32,
        Humidity: Number(f.humidity),
        Pressure: Number(f.pressureHpa) * 0.02953,
        Visibility_mi: Math.min(Number(f.visibilityKm) / 1.609, 100),
        Wind_Speed_mph: Number(f.windKmh) / 1.609,
        Precipitation_in: Number(f.precipMm) / 25.4,
        Weather_Condition: f.weather,
        Hour: d.getHours(), Month: d.getMonth() + 1, DayOfWeek: (d.getDay() + 6) % 7,
        IsNight: f.night,
        mode: f.mode, ...f.road,
      })
      setResult(data)
    } catch (e2) { setError(errorMessage(e2)) } finally { setLoading(false) }
  }

  const field = (k) => ({ k, value: f[k], onChange: num(k) })

  return (
    <div className="mx-auto max-w-page px-4 py-8 space-y-6">
      <header>
        <p className="eyebrow">Simulateur</p>
        <h1 className="mt-1 text-2xl sm:text-3xl font-bold tracking-tight">Tester un scénario</h1>
        <p className="mt-2 max-w-3xl text-soft">
          Choisissez un lieu, chargez la météo réelle ou saisissez vos propres conditions, et observez comment
          chaque facteur fait varier la prédiction du modèle.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-12">
        <form onSubmit={submit} className="lg:col-span-7 space-y-6">
          <Card title="Lieu et moment">
            <div className="space-y-4">
              <PlaceSearch label="Lieu" value={f.place} onChange={set("place")} placeholder="Ville, adresse…" allowLocate />
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="when">Date et heure (heure locale du lieu)</label>
                  <input id="when" type="datetime-local" className="field" value={f.when} onChange={(e) => set("when")(e.target.value)} required />
                </div>
                <div className="flex items-end">
                  <Toggle label="Il fait nuit" checked={f.night} onChange={set("night")} />
                </div>
              </div>
            </div>
          </Card>

          <Card title="Météo" action={
            <button type="button" className="btn-ghost py-1.5" onClick={fillWeather} disabled={fetching}>
              {fetching ? "Chargement…" : "☁ Météo actuelle"}
            </button>}>
            {weatherNote && <p className="mb-4 text-xs text-accent">{weatherNote}</p>}
            <div className="grid gap-4 grid-cols-2 sm:grid-cols-3">
              <NumField {...field("tempC")} label="Température" unit="°C" min={-50} max={60} />
              <NumField {...field("humidity")} label="Humidité" unit="%" min={0} max={100} />
              <NumField {...field("pressureHpa")} label="Pression" unit="hPa" min={850} max={1080} />
              <NumField {...field("visibilityKm")} label="Visibilité" unit="km" step={0.1} min={0} max={160} />
              <NumField {...field("windKmh")} label="Vent" unit="km/h" min={0} max={300} />
              <NumField {...field("precipMm")} label="Précipitations" unit="mm/h" step={0.1} min={0} max={600} />
            </div>
            <div className="mt-4">
              <label className="label" htmlFor="weather">Conditions</label>
              <select id="weather" className="field" value={f.weather} onChange={(e) => set("weather")(e.target.value)}>
                {Object.entries(WEATHER_FR).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          </Card>

          <Card title="Route et mode">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {ROAD.map(([k, l]) => (
                <Toggle key={k} label={l} checked={!!f.road[k]} onChange={(v) => setF((p) => ({ ...p, road: { ...p.road, [k]: v } }))} />
              ))}
            </div>
            <div className="mt-5">
              <span className="label">Mode d'alerte</span>
              <Segmented ariaLabel="Mode d'alerte" value={f.mode} onChange={set("mode")}
                options={Object.entries(MODES).map(([value, m]) => ({ value, label: m.label, hint: m.hint }))} />
              <p className="mt-1.5 text-xs text-muted">{MODES[f.mode].hint}</p>
            </div>
            <button type="submit" className="btn-primary mt-6 w-full py-3" disabled={loading}>
              {loading ? "Calcul…" : "Calculer le risque →"}
            </button>
          </Card>
        </form>

        <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-20 h-fit">
          {error && <Alert tone="error" title="Erreur">{error}</Alert>}
          {!result && !loading && (
            <div className="card card-pad text-center text-soft">
              <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-raised text-2xl" aria-hidden>⛉</div>
              Renseignez le scénario puis lancez le calcul pour voir le score et ses facteurs explicatifs.
            </div>
          )}
          {loading && <div className="card card-pad"><Spinner label="Prédiction en cours…" /></div>}
          {result && (
            <>
              {result.warnings.map((w) => <Alert key={w} tone="warning">{w}</Alert>)}
              <Card eyebrow="Résultat du modèle" title="Indice de risque">
                <RiskGauge score={result.risk_score} threshold={result.threshold_used} label={`Mode ${MODES[result.mode].label}`} />
                <div className={`mt-4 rounded-xl border px-4 py-3 text-sm ${result.is_high_risk ? "border-critical/50 bg-critical/10" : "border-good/40 bg-good/10"}`}>
                  <p className="font-semibold text-ink">
                    {result.is_high_risk ? "⚠ Au-dessus" : "✓ En dessous"} du seuil d'alerte ({Math.round(result.threshold_used * 100)})
                  </p>
                  <p className="mt-0.5 text-soft">{result.advice}</p>
                </div>
                <p className="mt-3 text-xs text-muted">État détecté : {result.inputs.State || "hors USA"}</p>
              </Card>
              <Card eyebrow="Explicabilité" title="Ce qui influence ce score">
                <FactorBars factors={result.explanation.factors} />
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
