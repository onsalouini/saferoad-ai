import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { CopilotIcon } from "../components/Assistant"
import { useAuth } from "../context/AuthContext"
import { api } from "../lib/api"
import { STATUS, fmt } from "../lib/risk"

const FEATURES = [
  {
    t: "Analyse de trajet", to: "/trajet",
    d: "Itinéraire réel découpé en tronçons, chacun évalué avec la météo prévue au moment exact où vous y passerez.",
    icon: <path d="M4 19c4 0 4-6 8-6s4-6 8-6M4 19h.01M20 7h.01" />,
  },
  {
    t: "Meilleure heure de départ", to: "/trajet",
    d: "24 heures de départs comparées : SafeRoad vous indique le créneau le plus sûr et combien de points vous gagnez.",
    icon: <><circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /></>,
  },
  {
    t: "Comparaison d'itinéraires", to: "/trajet",
    d: "Les itinéraires alternatifs sont notés côte à côte ; à risque égal, le plus rapide est recommandé.",
    icon: <path d="M6 4v6a4 4 0 004 4h4a4 4 0 014 4v2M18 4v6M6 20v-2" />,
  },
  {
    t: "Copilote IA", to: "/copilote", badge: "Nouveau",
    d: "Un assistant (Claude) qui lit votre analyse, rédige un briefing clair et répond à vos questions de conduite.",
    icon: <><path d="M12 3l1.8 4.6L18.5 9l-4.7 1.4L12 15l-1.8-4.6L5.5 9l4.7-1.4L12 3z" /><path d="M18 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" /></>,
  },
  {
    t: "Simulateur de scénarios", to: "/simulation",
    d: "Pluie, nuit, intersection… changez un facteur et voyez son effet sur le score, expliqué par SHAP.",
    icon: <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0M16 4v4M10 10v4M18 16v4" />,
  },
  {
    t: "Transparence du modèle", to: "/modele",
    d: "Performances, calibration, tests de cohérence et limites connues, publiés sans filtre.",
    icon: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
  },
]

const STEPS = [
  { t: "Saisissez votre trajet", d: "Adresse de départ et d'arrivée. L'itinéraire routier réel est calculé (OSRM / OpenStreetMap)." },
  { t: "Météo à l'heure de passage", d: "Pluie, neige, visibilité, vent et nuit sont prévus pour chaque tronçon (Open-Meteo)." },
  { t: "Le modèle évalue", d: "LightGBM, entraîné sur 7,7 M d'accidents, note chaque tronçon et explique ses facteurs." },
  { t: "Vous décidez", d: "Meilleur itinéraire, meilleur créneau, et un briefing du copilote IA en langage clair." },
]

const FAQ = [
  ["L'indice est-il la probabilité d'avoir un accident ?",
    "Non. Il estime la propension d'un accident à être grave dans des conditions données. C'est un indice relatif, idéal pour comparer des horaires ou des itinéraires, pas une probabilité absolue."],
  ["Fonctionne-t-il hors des États-Unis ?",
    "Le modèle a été entraîné sur des accidents américains. Ailleurs, l'analyse fonctionne mais le score est extrapolé : il est signalé comme indicatif."],
  ["Faut-il un compte ?",
    "Non pour analyser un trajet ou utiliser le simulateur. Un compte gratuit donne accès à l'historique de vos analyses et au copilote IA."],
  ["D'où viennent les données ?",
    "Accidents : US Accidents (Moosavi et al.). Cartes et adresses : OpenStreetMap / Nominatim. Itinéraires : OSRM. Météo : Open-Meteo."],
]

function Icon({ children }) {
  return (
    <span className="grid h-10 w-10 place-items-center rounded-xl bg-accent/15 text-accent">
      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden>{children}</svg>
    </span>
  )
}

// Illustration : un itinéraire coloré par niveau de risque et deux cartes de résultat
function HeroVisual() {
  const seg = [STATUS.good.hex, STATUS.good.hex, STATUS.warning.hex, STATUS.serious.hex, STATUS.warning.hex, STATUS.good.hex]
  return (
    <div className="relative mx-auto w-full max-w-md" aria-hidden>
      <div className="card overflow-hidden p-0">
        <div className="flex items-center gap-1.5 border-b border-line/60 px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-line" /><span className="h-2.5 w-2.5 rounded-full bg-line" /><span className="h-2.5 w-2.5 rounded-full bg-line" />
          <span className="ml-2 text-xs text-muted">Los Angeles → San Diego</span>
        </div>
        <svg viewBox="0 0 400 240" className="block w-full bg-page/60">
          <defs>
            <pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse">
              <path d="M24 0H0V24" fill="none" stroke="rgb(var(--line))" strokeOpacity=".45" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="400" height="240" fill="url(#grid)" />
          {[[40, 200, 90, 170], [90, 170, 140, 150], [140, 150, 200, 120], [200, 120, 250, 100], [250, 100, 310, 70], [310, 70, 360, 40]].map(([x1, y1, x2, y2], i) => (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke={seg[i]} strokeWidth="7" strokeLinecap="round" />
          ))}
          <circle cx="40" cy="200" r="8" fill="rgb(var(--surface))" stroke="rgb(var(--ink))" strokeWidth="3" />
          <circle cx="360" cy="40" r="8" fill="rgb(var(--accent))" stroke="rgb(var(--ink))" strokeWidth="3" />
          <circle cx="225" cy="110" r="14" fill="none" stroke={STATUS.serious.hex} strokeWidth="2" strokeDasharray="4 4" />
        </svg>
      </div>

      <div className="card absolute -left-4 -bottom-8 w-48 px-4 py-3 shadow-2xl shadow-black/40 sm:-left-10">
        <p className="text-[11px] text-muted">Indice du trajet</p>
        <p className="mt-0.5 flex items-baseline gap-2"><span className="text-3xl font-bold tnum">42</span><span className="text-xs text-soft">/ 100</span></p>
        <span className="mt-1 inline-flex items-center gap-1.5 rounded-full bg-raised px-2 py-0.5 text-xs font-semibold ring-1 ring-warning/40">
          <span className="text-warning">▲</span> Modéré
        </span>
      </div>

      <div className="card absolute -right-3 -top-6 w-52 px-4 py-3 shadow-2xl shadow-black/40 sm:-right-8">
        <p className="flex items-center gap-1.5 text-[11px] text-accent"><CopilotIcon className="h-3.5 w-3.5" /> Copilote IA</p>
        <p className="mt-1 text-xs leading-relaxed text-soft">
          Partez plutôt à <b className="text-ink">14 h</b> : la pluie aura cessé, l'indice baisse de <b className="text-ink">12 points</b>.
        </p>
      </div>
    </div>
  )
}

export default function Home() {
  const { user } = useAuth()
  const [info, setInfo] = useState(null)
  useEffect(() => { api.get("/model/info").then((r) => setInfo(r.data)).catch(() => {}) }, [])
  const ev = info?.evaluation

  const stats = [
    ["7,7 M", "accidents réels étudiés"],
    [info?.n_features ?? "94", "variables par situation"],
    [ev ? fmt.num(ev.metrics.roc_auc_distance_fixed, 2) : "0,89", "ROC-AUC mesuré"],
    ["24 h", "de départs comparés"],
  ]

  return (
    <div className="overflow-x-hidden">
      {/* Hero */}
      <section className="relative">
        <div className="pointer-events-none absolute inset-x-0 -top-24 h-[28rem] bg-[radial-gradient(ellipse_at_top,rgb(var(--accent)/0.18),transparent_65%)]" />
        <div className="relative mx-auto grid max-w-page items-center gap-14 px-4 py-14 lg:grid-cols-12 lg:py-24">
          <div className="lg:col-span-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-line/70 bg-surface/80 px-3 py-1 text-xs text-soft">
              <span className="h-1.5 w-1.5 rounded-full bg-good" /> Nouveau : briefing de trajet par IA
            </span>
            <h1 className="mt-5 text-4xl font-bold leading-[1.1] tracking-tight sm:text-5xl lg:text-6xl">
              Prenez la route<br />au <span className="text-accent">bon moment</span>,<br />par le <span className="text-accent">bon chemin</span>.
            </h1>
            <p className="mt-6 max-w-xl text-lg text-soft">
              SafeRoad AI croise 7,7 millions d'accidents, la météo prévue et votre itinéraire pour estimer le risque
              tronçon par tronçon, puis recommande l'horaire et l'itinéraire les plus sûrs.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/trajet" className="btn-primary px-6 py-3 text-base">Analyser un trajet →</Link>
              {user
                ? <Link to="/copilote" className="btn-ghost px-6 py-3 text-base"><CopilotIcon className="h-4 w-4" /> Parler au copilote</Link>
                : <Link to="/inscription" className="btn-ghost px-6 py-3 text-base">Créer un compte gratuit</Link>}
            </div>
            <p className="mt-6 text-xs text-muted">Gratuit · Sans installation · Données ouvertes OpenStreetMap, OSRM et Open-Meteo</p>
          </div>
          <div className="lg:col-span-6 px-6 pb-10 pt-6 sm:px-10">
            <HeroVisual />
          </div>
        </div>
      </section>

      {/* Chiffres */}
      <section className="border-y border-line/60 bg-surface/50">
        <dl className="mx-auto grid max-w-page grid-cols-2 gap-6 px-4 py-8 md:grid-cols-4">
          {stats.map(([v, l]) => (
            <div key={l} className="text-center">
              <dd className="text-3xl font-bold tnum">{v}</dd>
              <dt className="mt-1 text-sm text-muted">{l}</dt>
            </div>
          ))}
        </dl>
      </section>

      {/* Fonctionnalités */}
      <section className="mx-auto max-w-page px-4 py-20">
        <div className="max-w-2xl">
          <p className="eyebrow text-accent">Fonctionnalités</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Tout ce qu'il faut pour décider avant de partir</h2>
          <p className="mt-3 text-soft">Une analyse complète en quelques secondes, expliquée plutôt qu'imposée.</p>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <Link key={f.t} to={f.to} className="card card-pad group transition hover:-translate-y-0.5 hover:border-accent/60">
              <div className="flex items-start justify-between">
                <Icon>{f.icon}</Icon>
                {f.badge && <span className="rounded-full bg-accent/15 px-2 py-0.5 text-xs font-semibold text-accent">{f.badge}</span>}
              </div>
              <h3 className="mt-4 font-semibold group-hover:text-accent">{f.t}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-soft">{f.d}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Comment ça marche */}
      <section className="border-y border-line/60 bg-surface/50">
        <div className="mx-auto max-w-page px-4 py-20">
          <p className="eyebrow text-accent">Comment ça marche</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">De l'adresse à la décision, en 4 étapes</h2>
          <ol className="mt-10 grid gap-8 md:grid-cols-4">
            {STEPS.map((s, i) => (
              <li key={s.t} className="relative">
                <div className="flex items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-strong text-sm font-bold text-white">{i + 1}</span>
                  {i < STEPS.length - 1 && <span className="hidden h-px flex-1 bg-line md:block" />}
                </div>
                <h3 className="mt-4 font-semibold">{s.t}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-soft">{s.d}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* Copilote IA */}
      <section className="mx-auto grid max-w-page items-center gap-12 px-4 py-20 lg:grid-cols-2">
        <div>
          <p className="eyebrow text-accent">Copilote IA</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight">Les chiffres, expliqués comme par un instructeur</h2>
          <p className="mt-4 text-soft">
            Le copilote lit votre analyse (tronçons, météo au passage, créneaux, facteurs SHAP) et la traduit en
            conseils concrets. Posez-lui vos questions : quel itinéraire choisir, pourquoi ce tronçon, comment conduire
            sous la neige…
          </p>
          <ul className="mt-6 space-y-2 text-sm text-soft">
            {["Briefing de trajet en un clic", "Réponses fondées sur les chiffres de votre analyse", "Honnête sur les limites du modèle"].map((x) => (
              <li key={x} className="flex gap-2"><span className="text-good">✓</span>{x}</li>
            ))}
          </ul>
          <Link to={user ? "/copilote" : "/inscription"} className="btn-primary mt-8">{user ? "Ouvrir le copilote →" : "Créer un compte pour l'essayer →"}</Link>
        </div>
        <div className="card card-pad space-y-4" aria-hidden>
          <div className="flex justify-end">
            <p className="max-w-[80%] rounded-2xl rounded-br-md bg-accent-strong px-4 py-2.5 text-sm text-white">Fais-moi un briefing de ce trajet</p>
          </div>
          <div className="flex gap-2.5">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent/15 text-accent"><CopilotIcon className="h-4 w-4" /></span>
            <div className="max-w-[85%] space-y-2 rounded-2xl rounded-bl-md bg-raised px-4 py-3 text-sm leading-relaxed text-soft">
              <p><b className="text-ink">Risque modéré (42/100)</b>, sous le seuil d'alerte Standard.</p>
              <p>Le point sensible est le <b className="text-ink">km 85</b> : pluie forte prévue à votre passage, de nuit.</p>
              <ul className="list-disc space-y-1 pl-5">
                <li>Partir à <b className="text-ink">14 h</b> fait baisser l'indice de 12 points.</li>
                <li>Allongez vos distances de sécurité sous la pluie.</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Honnêteté */}
      <section className="mx-auto max-w-page px-4 pb-20">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="card card-pad">
            <p className="eyebrow text-good">Ce que SafeRoad fait bien</p>
            <ul className="mt-3 space-y-2 text-sm text-soft">
              <li>✓ Classer des situations de la plus à la moins risquée (AUC ≈ 0,89)</li>
              <li>✓ Réagir de façon cohérente à la pluie, la neige, le brouillard et la nuit</li>
              <li>✓ Comparer des horaires et des itinéraires entre eux</li>
            </ul>
          </div>
          <div className="card card-pad">
            <p className="eyebrow text-warning">Ce qu'il ne fait pas</p>
            <ul className="mt-3 space-y-2 text-sm text-soft">
              <li>✕ Prédire qu'un accident va se produire</li>
              <li>✕ Donner une probabilité absolue (score non calibré)</li>
              <li>✕ Connaître le trafic ou les travaux en temps réel</li>
            </ul>
            <Link to="/modele" className="mt-4 inline-block text-sm text-accent hover:underline">Lire le rapport d'évaluation →</Link>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="border-t border-line/60 bg-surface/50">
        <div className="mx-auto max-w-3xl px-4 py-20">
          <h2 className="text-center text-3xl font-bold tracking-tight">Questions fréquentes</h2>
          <div className="mt-8 space-y-3">
            {FAQ.map(([q, a]) => (
              <details key={q} className="card group px-5 py-4 open:border-accent/50">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium">
                  {q}<span className="text-muted transition group-open:rotate-45" aria-hidden>+</span>
                </summary>
                <p className="mt-3 text-sm leading-relaxed text-soft">{a}</p>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* Appel final */}
      <section className="mx-auto max-w-page px-4 py-20">
        <div className="relative overflow-hidden rounded-3xl border border-accent/40 bg-gradient-to-br from-accent-strong/30 via-surface to-surface px-6 py-14 text-center">
          <h2 className="text-3xl font-bold tracking-tight">Votre prochain trajet mérite une vérification</h2>
          <p className="mx-auto mt-3 max-w-xl text-soft">30 secondes pour savoir quand partir et par où passer.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/trajet" className="btn-primary px-6 py-3 text-base">Analyser un trajet →</Link>
            {!user && <Link to="/inscription" className="btn-ghost px-6 py-3 text-base">Créer un compte</Link>}
          </div>
        </div>
      </section>
    </div>
  )
}
