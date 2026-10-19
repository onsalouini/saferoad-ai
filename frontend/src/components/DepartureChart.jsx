import { useState } from "react"
import { STATUS, fmt } from "../lib/risk"

/**
 * Indice de risque moyen du trajet selon l'heure de départ (24 h).
 * Colonnes colorées par niveau (statut) ; seuil du mode en ligne de référence.
 */
export default function DepartureChart({ departures = [], threshold, best }) {
  const [hover, setHover] = useState(null)
  if (!departures.length) return null
  const W = 720, H = 220, padL = 34, padR = 8, padT = 14, padB = 30
  const plotW = W - padL - padR, plotH = H - padT - padB
  const n = departures.length
  const band = plotW / n
  const barW = Math.min(24, band - 2)
  const y = (v) => padT + plotH - (v / 100) * plotH
  const ticks = [0, 25, 50, 75, 100]
  const h = hover != null ? departures[hover] : null

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img"
        aria-label="Indice de risque selon l'heure de départ sur 24 heures">
        {ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="rgb(var(--line))" strokeWidth="1" />
            <text x={padL - 6} y={y(t) + 3} textAnchor="end" fontSize="10" fill="rgb(var(--muted))" className="tnum">{t}</text>
          </g>
        ))}
        {threshold != null && (
          <g>
            <line x1={padL} x2={W - padR} y1={y(threshold * 100)} y2={y(threshold * 100)}
              stroke="rgb(var(--ink))" strokeOpacity="0.7" strokeWidth="1.5" />
          </g>
        )}
        {departures.map((d, i) => {
          const x = padL + i * band + (band - barW) / 2
          const top = y(d.risk_score)
          const hgt = padT + plotH - top
          const isBest = best && d.time === best.time
          const r = Math.min(4, hgt)
          return (
            <g key={d.time} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)} onBlur={() => setHover(null)} tabIndex={0}>
              <rect x={padL + i * band} y={padT} width={band} height={plotH} fill="transparent" />
              <path
                d={`M${x},${padT + plotH} V${top + r} Q${x},${top} ${x + r},${top} H${x + barW - r} Q${x + barW},${top} ${x + barW},${top + r} V${padT + plotH} Z`}
                fill={STATUS[d.status].hex}
                opacity={hover == null || hover === i ? 1 : 0.45}
              />
              {isBest && (
                <text x={x + barW / 2} y={top - 6} textAnchor="middle" fontSize="10" fontWeight="700" fill="rgb(var(--ink))">
                  ★ {Math.round(d.risk_score)}
                </text>
              )}
              {(i % 3 === 0) && (
                <text x={x + barW / 2} y={H - 10} textAnchor="middle" fontSize="10" fill="rgb(var(--muted))" className="tnum">
                  {fmt.hour(d.time).slice(0, 2)}h
                </text>
              )}
            </g>
          )
        })}
        <line x1={padL} x2={W - padR} y1={padT + plotH} y2={padT + plotH} stroke="rgb(var(--muted))" strokeWidth="1" />
      </svg>

      {h && (
        <div className="pointer-events-none absolute top-0 z-10 rounded-lg border border-line bg-raised px-3 py-2 text-xs shadow-lg"
          style={{ left: `${Math.min(80, Math.max(0, ((padL + hover * band) / W) * 100 - 8))}%` }}>
          <div className="font-semibold text-ink">Départ {fmt.dayHour(h.time)}</div>
          <div className="mt-1 flex items-center gap-1.5 text-soft">
            <span className={STATUS[h.status].text}>{STATUS[h.status].icon}</span>
            Indice moyen <b className="text-ink tnum">{fmt.num(h.risk_score)}</b> · {STATUS[h.status].label}
          </div>
          <div className="text-soft">Pic sur le trajet : <span className="tnum text-ink">{fmt.num(h.peak_score)}</span></div>
          <div className="text-muted">{h.weather_label} au départ</div>
        </div>
      )}

      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-soft">
        {Object.entries(STATUS).map(([k, s]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.hex }} />{s.label}
          </span>
        ))}
        {threshold != null && (
          <span className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 bg-ink/70" />Seuil d'alerte du mode ({Math.round(threshold * 100)})
          </span>
        )}
        <span className="text-muted">★ meilleur créneau</span>
      </div>
    </div>
  )
}
