import { useState } from "react"
import { fmt } from "../lib/risk"

/**
 * Contributions SHAP (log-odds) par facteur : barres divergentes autour de 0.
 * Rouge = le facteur fait monter le risque, bleu = il le fait baisser.
 */
export default function FactorBars({ factors = [] }) {
  const [hover, setHover] = useState(null)
  if (!factors.length) return <p className="text-sm text-muted">Aucun facteur significatif.</p>
  const max = Math.max(...factors.map((f) => Math.abs(f.impact)), 0.01)

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-4 text-xs text-soft">
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-up" />Augmente le risque</span>
        <span className="inline-flex items-center gap-1.5"><span className="h-2.5 w-2.5 rounded-sm bg-down" />Diminue le risque</span>
      </div>
      <ul className="space-y-1.5" aria-label="Facteurs explicatifs">
        {factors.map((f, i) => {
          // 36 % max de chaque côté : laisse la place à la valeur affichée au bout de la barre
          const w = (Math.abs(f.impact) / max) * 36
          const up = f.impact > 0
          return (
            <li key={f.feature}
              className={`grid grid-cols-[minmax(0,9.5rem)_1fr] sm:grid-cols-[minmax(0,12rem)_1fr] items-center gap-3 rounded-lg px-2 py-1 ${hover === i ? "bg-raised" : ""}`}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
              <span className="truncate text-sm text-soft" title={f.label}>{f.label}</span>
              <div className="relative h-5">
                <div className="absolute inset-y-0 left-1/2 w-px bg-line" />
                <div
                  className={`absolute top-1/2 h-3 -translate-y-1/2 ${up ? "bg-up rounded-r" : "bg-down rounded-l"}`}
                  style={up ? { left: "50%", width: `${w}%` } : { right: "50%", width: `${w}%` }}
                />
                <span className="absolute top-1/2 -translate-y-1/2 text-xs tnum text-soft whitespace-nowrap"
                  style={up ? { left: `calc(50% + ${w}% + 6px)` } : { right: `calc(50% + ${w}% + 6px)` }}>
                  {up ? "+" : "−"}{fmt.num(Math.abs(f.impact), 2)}
                </span>
              </div>
            </li>
          )
        })}
      </ul>
      <p className="mt-3 text-xs text-muted">
        Contributions SHAP calculées par LightGBM pour cette prédiction (échelle log-odds).
        Plus la barre est longue, plus le facteur pèse sur le score.
      </p>
    </div>
  )
}
