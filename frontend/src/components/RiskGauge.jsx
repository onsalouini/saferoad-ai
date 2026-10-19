import { LEVEL_BOUNDS, STATUS, statusOf } from "../lib/risk"
import { StatusBadge } from "./ui"

// Demi-cercle : centre (100,100), rayon 80. Angle 180° (gauche) -> 0° (droite).
const R = 80
const point = (v) => {
  const a = Math.PI * (1 - v / 100)
  return [100 + R * Math.cos(a), 100 - R * Math.sin(a)]
}
const arc = (from, to) => {
  const [x0, y0] = point(from)
  const [x1, y1] = point(to)
  return `M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x1} ${y1}`
}

/** Jauge de l'indice de risque (0-100) avec bandes de niveaux et repère de seuil. */
export default function RiskGauge({ score = 0, threshold, label = "Indice de risque" }) {
  const v = Math.max(0, Math.min(100, Number(score) || 0))
  const status = statusOf(v)
  const [nx, ny] = point(v)
  const t = threshold != null ? threshold * 100 : null

  return (
    <figure className="flex flex-col items-center">
      <svg viewBox="0 0 200 118" className="w-full max-w-[260px]" role="img"
        aria-label={`${label} : ${v} sur 100, niveau ${STATUS[status].label}`}>
        {LEVEL_BOUNDS.map((b) => (
          <path key={b.status} d={arc(b.from + 0.6, b.to - 0.6)} fill="none"
            stroke={STATUS[b.status].hex} strokeOpacity="0.22" strokeWidth="14" />
        ))}
        {v > 0.5 && (
          <path d={arc(0, v)} fill="none" stroke={STATUS[status].hex} strokeWidth="14" strokeLinecap="round" />
        )}
        {t != null && (() => {
          const [ax, ay] = point(t)
          const [bx, by] = [100 + (ax - 100) * 1.16, 100 + (ay - 100) * 1.16]
          return (
            <g>
              <line x1={100 + (ax - 100) * 0.8} y1={100 + (ay - 100) * 0.8} x2={bx} y2={by}
                stroke="rgb(var(--ink))" strokeWidth="2" />
              <title>Seuil d'alerte du mode : {Math.round(t)}</title>
            </g>
          )
        })()}
        <circle cx={nx} cy={ny} r="6" fill={STATUS[status].hex} stroke="rgb(var(--surface))" strokeWidth="2" />
        <text x="100" y="92" textAnchor="middle" fill="rgb(var(--ink))" fontSize="34" fontWeight="700">
          {Math.round(v)}
        </text>
        <text x="100" y="110" textAnchor="middle" fill="rgb(var(--muted))" fontSize="10">
          / 100
        </text>
      </svg>
      <figcaption className="mt-1 flex flex-col items-center gap-1.5">
        <StatusBadge status={status} size="lg" />
        <span className="text-xs text-muted">{label}</span>
      </figcaption>
    </figure>
  )
}
