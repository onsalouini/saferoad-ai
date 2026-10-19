import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { api } from "../lib/api"
import { fmt } from "../lib/risk"

const STEPS = [
  { n: "1", t: "Votre itinéraire", d: "Départ et arrivée : l'itinéraire routier réel est calculé (OSRM / OpenStreetMap) et découpé en tronçons." },
  { n: "2", t: "Météo à l'heure de passage", d: "Pour chaque tronçon, la météo prévue au moment où vous y serez (Open-Meteo) : pluie, neige, visibilité, vent, nuit." },
  { n: "3", t: "Prédiction expliquée", d: "Le modèle LightGBM évalue chaque tronçon, explique les facteurs déterminants et propose le créneau de départ le plus sûr." },
]

export default function Home() {
  const [info, setInfo] = useState(null)
  useEffect(() => { api.get("/model/info").then((r) => setInfo(r.data)).catch(() => {}) }, [])
  const ev = info?.evaluation

  return (
    <div className="mx-auto max-w-page px-4">
      <section className="grid gap-10 py-14 lg:grid-cols-12 lg:py-20 items-center">
        <div className="lg:col-span-7">
          <p className="eyebrow text-accent">Sécurité routière · Intelligence artificielle</p>
          <h1 className="mt-3 text-4xl sm:text-5xl font-bold tracking-tight leading-tight">
            Anticipez le risque de votre trajet <span className="text-accent">avant de prendre la route</span>.
          </h1>
          <p className="mt-5 max-w-2xl text-lg text-soft">
            SafeRoad AI croise l'historique de 7,7 millions d'accidents, la météo prévue et votre itinéraire pour
            estimer le risque tronçon par tronçon, puis recommande l'itinéraire et l'horaire les plus sûrs.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link to="/trajet" className="btn-primary px-6 py-3 text-base">Analyser un trajet →</Link>
            <Link to="/modele" className="btn-ghost px-6 py-3 text-base">Voir la fiabilité du modèle</Link>
          </div>
        </div>

        <div className="lg:col-span-5">
          <div className="card card-pad">
            <p className="eyebrow">Le modèle en chiffres</p>
            <dl className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <dt className="text-xs text-muted">ROC-AUC mesuré</dt>
                <dd className="mt-1 text-3xl font-bold">{ev ? fmt.num(ev.metrics.roc_auc_distance_fixed, 3) : "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Accidents d'entraînement</dt>
                <dd className="mt-1 text-3xl font-bold">7,7 M</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Variables</dt>
                <dd className="mt-1 text-3xl font-bold">{info?.n_features ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Rappel (mode Standard)</dt>
                <dd className="mt-1 text-3xl font-bold">{ev ? fmt.pct(ev.thresholds.find((t) => t.mode === "standard").recall, 0) : "—"}</dd>
              </div>
            </dl>
            <p className="mt-5 border-t border-line/60 pt-4 text-xs text-muted">
              LightGBM entraîné sur le jeu de données US Accidents (2016-2023). Évaluation indépendante sur
              {ev ? ` ${fmt.int(ev.dataset.rows_evaluated)}` : ""} accidents réels — détails et limites sur la page « Le modèle ».
            </p>
          </div>
        </div>
      </section>

      <section className="pb-16">
        <h2 className="text-xl font-semibold">Comment ça marche</h2>
        <ol className="mt-5 grid gap-4 md:grid-cols-3">
          {STEPS.map((s) => (
            <li key={s.n} className="card card-pad">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-accent/15 text-sm font-bold text-accent">{s.n}</span>
              <h3 className="mt-3 font-semibold">{s.t}</h3>
              <p className="mt-1.5 text-sm text-soft leading-relaxed">{s.d}</p>
            </li>
          ))}
        </ol>

        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {[
            ["Simulateur de scénarios", "Testez l'effet de la pluie, de la nuit ou d'une intersection sur le score.", "/simulation"],
            ["Transparence du modèle", "Performances, calibration, tests de cohérence et limites, en toute honnêteté.", "/modele"],
            ["Historique personnel", "Connectez-vous pour retrouver et relancer vos analyses.", "/historique"],
          ].map(([t, d, to]) => (
            <Link key={to} to={to} className="card card-pad group hover:border-accent/60 transition">
              <h3 className="font-semibold group-hover:text-accent">{t} →</h3>
              <p className="mt-1.5 text-sm text-soft">{d}</p>
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
