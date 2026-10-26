import { Fragment, useEffect, useRef, useState } from "react"
import { Link } from "react-router-dom"
import { useAuth } from "../context/AuthContext"
import { api } from "../lib/api"
import { streamChat } from "../lib/assistant"
import { fmt } from "../lib/risk"
import { speak, speechSupported, stopSpeaking, useDictation } from "../lib/voice"
import { Alert } from "./ui"

// Rendu minimal du texte du copilote : paragraphes, listes « - » et **gras** (React échappe le reste)
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? <b key={i} className="text-ink">{part.slice(2, -2)}</b> : <Fragment key={i}>{part}</Fragment>)
}

function RichText({ text }) {
  const blocks = text.trim().split(/\n{2,}/)
  return blocks.map((block, i) => {
    const lines = block.split("\n")
    if (lines.every((l) => /^\s*[-•*]\s+/.test(l))) {
      return (
        <ul key={i} className="my-2 list-disc space-y-1 pl-5">
          {lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*[-•*]\s+/, ""))}</li>)}
        </ul>
      )
    }
    return <p key={i} className="my-2 first:mt-0 last:mb-0">{inline(block)}</p>
  })
}

export function CopilotIcon({ className = "h-5 w-5" }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M12 3l1.8 4.6L18.5 9l-4.7 1.4L12 15l-1.8-4.6L5.5 9l4.7-1.4L12 3z" />
      <path d="M18 15l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" />
    </svg>
  )
}

function tripLink(t) {
  const enc = (p) => `${p.lat.toFixed(5)},${p.lng.toFixed(5)},${p.label || ""}`
  return `/trajet?de=${encodeURIComponent(enc(t.origin))}&a=${encodeURIComponent(enc(t.destination))}&mode=${t.mode}`
}

function TripCard({ trip }) {
  return (
    <Link to={tripLink(trip)} className="mt-2 block rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-xs transition hover:border-accent">
      <span className="font-semibold text-ink">{trip.origin.label} → {trip.destination.label}</span>
      <span className="block text-soft">
        Indice {fmt.num(trip.risk_score)} ({trip.level}) · meilleur départ {fmt.dayHour(trip.best_departure)} · ouvrir l'analyse →
      </span>
    </Link>
  )
}

/**
 * Fenêtre de discussion avec le copilote IA.
 * context : résumé de l'analyse affichée (facultatif) ; suggestions : questions proposées.
 * Pour repartir d'une conversation vide quand l'analyse change, le parent change la `key`.
 */
export default function Assistant({ context, suggestions = [], intro, autoPrompt, height = "h-[26rem]" }) {
  const { user } = useAuth()
  const [status, setStatus] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [readAloud, setReadAloud] = useState(false)
  const abort = useRef(null)
  const scroller = useRef(null)
  const dictation = useDictation((text) => setInput((v) => (v ? `${v} ${text}` : text)))

  useEffect(() => { api.get("/assistant/status").then((r) => setStatus(r.data)).catch(() => setStatus({ available: false })) }, [])

  useEffect(() => () => { abort.current?.abort(); stopSpeaking() }, [])

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight })
  }, [messages])

  const updateLast = (fn) => setMessages((m) => [...m.slice(0, -1), fn(m[m.length - 1])])

  const send = async (text) => {
    const content = text.trim()
    if (!content || busy) return
    stopSpeaking()
    const history = [...messages, { role: "user", content }]
    setMessages([...history, { role: "assistant", content: "", tools: [], trips: [] }])
    setInput(""); setBusy(true); setError(null)
    const controller = new AbortController()
    abort.current = controller
    let answer = ""
    try {
      await streamChat({
        messages: history.map(({ role, content: c }) => ({ role, content: c })),
        context, signal: controller.signal,
        onEvent: (e) => {
          if (e.type === "text") { answer += e.text; updateLast((last) => ({ ...last, content: last.content + e.text })) }
          if (e.type === "tool") updateLast((last) => ({ ...last, tools: [...last.tools, e.label] }))
          if (e.type === "trip") updateLast((last) => ({ ...last, trips: [...last.trips, e] }))
          if (e.type === "error") setError(e.message)
        },
      })
      if (!answer.trim()) {
        setMessages(history.slice(0, -1)); setInput(content)
      } else if (readAloud) speak(answer)
    } catch (err) {
      if (err.name === "AbortError") return
      setError(err.message)
      setMessages(history.slice(0, -1))
      setInput(content)
    } finally {
      if (abort.current === controller) setBusy(false)
    }
  }

  if (status && !status.available) {
    return <Alert tone="info" title="Copilote IA désactivé">Le serveur n'a pas de clé Claude API (ANTHROPIC_API_KEY dans api/.env).</Alert>
  }
  if (!user) {
    return (
      <div className="rounded-xl border border-accent/40 bg-accent/10 px-5 py-6 text-center">
        <CopilotIcon className="mx-auto h-7 w-7 text-accent" />
        <p className="mt-2 font-semibold">Le copilote IA est réservé aux membres</p>
        <p className="mt-1 text-sm text-soft">Créez un compte gratuit pour lui poser vos questions sur vos trajets.</p>
        <div className="mt-4 flex justify-center gap-2">
          <Link to="/inscription" className="btn-primary">Créer un compte</Link>
          <Link to="/connexion" className="btn-ghost">Se connecter</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col">
      <div ref={scroller} className={`${height} overflow-y-auto rounded-xl border border-line/60 bg-page/60 p-4 space-y-4`} aria-live="polite">
        {messages.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <span className="grid h-11 w-11 place-items-center rounded-xl bg-accent/15 text-accent"><CopilotIcon className="h-6 w-6" /></span>
            <p className="mt-3 max-w-sm text-sm text-soft">{intro || "Posez une question sur la sécurité de votre trajet."}</p>
            {autoPrompt && (
              <button type="button" onClick={() => send(autoPrompt)} className="btn-primary mt-4">
                <CopilotIcon className="h-4 w-4" /> {autoPrompt}
              </button>
            )}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start gap-2.5"}`}>
            {m.role === "assistant" && (
              <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent/15 text-accent"><CopilotIcon className="h-4 w-4" /></span>
            )}
            <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              m.role === "user" ? "bg-accent-strong text-white rounded-br-md" : "bg-raised text-soft rounded-bl-md"}`}>
              {m.tools?.length > 0 && (
                <div className="mb-2 flex flex-wrap gap-1.5">
                  {m.tools.map((t, j) => (
                    <span key={j} className="inline-flex items-center gap-1 rounded-full bg-page/70 px-2 py-0.5 text-[11px] text-muted">⚙ {t}</span>
                  ))}
                </div>
              )}
              {m.role === "user" && m.content}
              {m.role === "assistant" && (m.content
                ? <RichText text={m.content} />
                : <span className="inline-flex gap-1" aria-label="Le copilote rédige"><Dot /><Dot d="150ms" /><Dot d="300ms" /></span>)}
              {m.trips?.map((t, j) => <TripCard key={j} trip={t} />)}
              {m.role === "assistant" && m.content && !busy && speechSupported && (
                <button type="button" onClick={() => speak(m.content)} className="mt-2 text-[11px] text-muted hover:text-ink">🔊 Écouter</button>
              )}
            </div>
          </div>
        ))}
      </div>

      {error && <div className="mt-3"><Alert tone="error">{error}</Alert></div>}

      {suggestions.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button key={s} type="button" onClick={() => send(s)} disabled={busy}
              className="rounded-full border border-line/70 bg-raised/60 px-3 py-1 text-xs text-soft transition hover:border-accent/60 hover:text-ink disabled:opacity-50">
              {s}
            </button>
          ))}
        </div>
      )}

      <form onSubmit={(e) => { e.preventDefault(); send(input) }} className="mt-3 flex gap-2">
        <label htmlFor="copilot-input" className="sr-only">Votre question</label>
        <input id="copilot-input" className="field py-2.5" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder={dictation.listening ? "Je vous écoute…" : "Ex. : Est-ce prudent de partir ce soir ?"} maxLength={4000} autoComplete="off" />
        {dictation.supported && (
          <button type="button" onClick={dictation.toggle} aria-pressed={dictation.listening}
            className={`btn-ghost shrink-0 px-3 ${dictation.listening ? "ring-2 ring-critical text-critical" : ""}`}
            title="Dicter la question" aria-label={dictation.listening ? "Arrêter la dictée" : "Dicter la question"}>🎙</button>
        )}
        {busy
          ? <button type="button" onClick={() => { abort.current?.abort(); setBusy(false) }} className="btn-ghost shrink-0">Arrêter</button>
          : <button type="submit" className="btn-primary shrink-0" disabled={!input.trim()}>Envoyer</button>}
      </form>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] text-muted">Réponses générées par IA (Claude), qui peut lancer des analyses. Vérifiez toujours les conditions réelles.</p>
        {speechSupported && (
          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-soft">
            <input type="checkbox" checked={readAloud} onChange={(e) => { setReadAloud(e.target.checked); if (!e.target.checked) stopSpeaking() }}
              className="h-3.5 w-3.5 accent-[rgb(var(--accent))]" />
            Lire les réponses à voix haute
          </label>
        )}
      </div>
    </div>
  )
}

function Dot({ d = "0ms" }) {
  return <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-muted" style={{ animationDelay: d }} />
}
