import { STATUS, statusOf } from "../lib/risk"

export function Card({ title, eyebrow, action, children, className = "", bodyClass = "card-pad" }) {
  return (
    <section className={`card ${className}`}>
      {(title || eyebrow || action) && (
        <header className="flex items-start justify-between gap-3 px-5 sm:px-6 pt-5">
          <div>
            {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
            {title && <h2 className="h-section">{title}</h2>}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  )
}

export function StatusBadge({ status, score, size = "md" }) {
  const s = STATUS[status || statusOf(score)]
  const pad = size === "lg" ? "px-3 py-1.5 text-sm" : "px-2 py-0.5 text-xs"
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-raised ring-1 ${s.ring} ${pad} font-semibold text-ink`}>
      <span className={s.text} aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  )
}

export function Stat({ label, value, unit, hint }) {
  return (
    <div className="rounded-xl bg-raised/60 border border-line/60 px-4 py-3">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-xl font-semibold text-ink">
        {value}
        {unit && <span className="ml-1 text-sm font-normal text-soft">{unit}</span>}
      </div>
      {hint && <div className="mt-0.5 text-xs text-muted">{hint}</div>}
    </div>
  )
}

export function Alert({ tone = "info", title, children }) {
  const tones = {
    info: "border-accent/40 bg-accent/10",
    warning: "border-warning/40 bg-warning/10",
    error: "border-critical/50 bg-critical/10",
  }
  const icons = { info: "ℹ", warning: "⚠", error: "✕" }
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex gap-3 rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>
      <span aria-hidden className="mt-0.5 font-bold">{icons[tone]}</span>
      <div className="text-soft">
        {title && <p className="font-semibold text-ink mb-0.5">{title}</p>}
        {children}
      </div>
    </div>
  )
}

export function Spinner({ label = "Chargement…" }) {
  return (
    <span className="inline-flex items-center gap-2 text-sm text-soft" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label}
    </span>
  )
}

export function Segmented({ value, onChange, options, ariaLabel }) {
  return (
    <div role="radiogroup" aria-label={ariaLabel} className="inline-flex rounded-xl bg-raised p-1 border border-line/60">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          title={o.hint}
          onClick={() => onChange(o.value)}
          className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
            value === o.value ? "bg-accent-strong text-white" : "text-soft hover:text-ink"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex items-center gap-2.5 cursor-pointer select-none text-sm text-soft hover:text-ink">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 rounded border-line bg-raised accent-[rgb(var(--accent))]" />
      {label}
    </label>
  )
}
