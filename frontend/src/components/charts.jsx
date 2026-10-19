import { useState } from "react"
import { fmt } from "../lib/risk"

/** Barres horizontales, une seule série (le titre de la carte nomme la mesure). */
export function HBarList({ items, max, format = (v) => fmt.num(v, 3), color = "rgb(var(--accent))", labelWidth = "12rem" }) {
  const [hover, setHover] = useState(null)
  const m = max ?? Math.max(...items.map((i) => i.value), 1e-9)
  return (
    <ul className="space-y-2">
      {items.map((it, i) => (
        <li key={it.label} className="grid items-center gap-3" style={{ gridTemplateColumns: `minmax(0,${labelWidth}) 1fr` }}
          onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
          <span className="truncate text-sm text-soft" title={it.label}>{it.label}</span>
          <div className="flex items-center gap-2">
            <div className="h-3 rounded-r" style={{
              width: `${Math.max(0.5, (it.value / m) * 85)}%`, background: color,
              opacity: hover == null || hover === i ? 1 : 0.5,
            }} />
            <span className="text-xs tnum text-soft whitespace-nowrap">{format(it.value)}</span>
          </div>
        </li>
      ))}
    </ul>
  )
}

/** Diagramme de fiabilité : probabilité prédite vs fréquence observée, diagonale = calibration parfaite. */
export function CalibrationChart({ bins }) {
  const [hover, setHover] = useState(null)
  const W = 420, H = 300, pl = 40, pr = 12, pt = 12, pb = 36
  const x = (v) => pl + v * (W - pl - pr)
  const y = (v) => pt + (1 - v) * (H - pt - pb)
  const ticks = [0, 0.25, 0.5, 0.75, 1]
  const path = bins.map((b, i) => `${i ? "L" : "M"}${x(b.predicted)},${y(b.observed)}`).join(" ")
  const h = hover != null ? bins[hover] : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        aria-label="Courbe de calibration : fréquence observée en fonction de la probabilité prédite">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pl} x2={W - pr} y1={y(t)} y2={y(t)} stroke="rgb(var(--line))" />
            <text x={pl - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="rgb(var(--muted))">{t * 100}%</text>
            <text x={x(t)} y={H - pb + 14} textAnchor="middle" fontSize="10" fill="rgb(var(--muted))">{t * 100}%</text>
          </g>
        ))}
        <text x={(W + pl) / 2} y={H - 4} textAnchor="middle" fontSize="10" fill="rgb(var(--soft))">Score prédit par le modèle</text>
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="rgb(var(--muted))" strokeWidth="1.5" strokeDasharray="4 4" />
        <text x={x(0.62)} y={y(0.7)} fontSize="10" fill="rgb(var(--muted))" transform={`rotate(-35 ${x(0.62)} ${y(0.7)})`}>calibration parfaite</text>
        <path d={path} fill="none" stroke="rgb(var(--accent))" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {bins.map((b, i) => (
          <g key={b.bin} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
            <circle cx={x(b.predicted)} cy={y(b.observed)} r="12" fill="transparent" />
            <circle cx={x(b.predicted)} cy={y(b.observed)} r={hover === i ? 6 : 4.5}
              fill="rgb(var(--accent))" stroke="rgb(var(--surface))" strokeWidth="2" />
          </g>
        ))}
      </svg>
      {h && (
        <div className="pointer-events-none absolute right-2 top-2 rounded-lg border border-line bg-raised px-3 py-2 text-xs">
          <div className="font-semibold text-ink">Scores {h.bin.replace("-", " – ")}</div>
          <div className="text-soft">Moyenne prédite : <b className="text-ink">{fmt.pct(h.predicted)}</b></div>
          <div className="text-soft">Accidents graves observés : <b className="text-ink">{fmt.pct(h.observed)}</b></div>
          <div className="text-muted">{fmt.int(h.count)} accidents</div>
        </div>
      )}
    </div>
  )
}
