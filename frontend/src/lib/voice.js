import { useCallback, useEffect, useRef, useState } from "react"

// Synthèse vocale (lecture des réponses) et reconnaissance vocale (dictée) du navigateur, en français.
export const speechSupported = typeof window !== "undefined" && "speechSynthesis" in window
const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition)

/** Retire la mise en forme (gras, puces) avant lecture. */
function plain(text) {
  return text.replace(/\*\*/g, "").replace(/^\s*[-•*]\s+/gm, "").replace(/\s+/g, " ").trim()
}

export function speak(text) {
  if (!speechSupported || !text) return
  window.speechSynthesis.cancel()
  const u = new SpeechSynthesisUtterance(plain(text))
  u.lang = "fr-FR"
  u.rate = 1.02
  const voice = window.speechSynthesis.getVoices().find((v) => v.lang?.startsWith("fr"))
  if (voice) u.voice = voice
  window.speechSynthesis.speak(u)
}

export function stopSpeaking() {
  if (speechSupported) window.speechSynthesis.cancel()
}

/** Dictée : onText(texte reconnu) à la fin de chaque phrase. */
export function useDictation(onText) {
  const [listening, setListening] = useState(false)
  const rec = useRef(null)
  const cb = useRef(onText)
  useEffect(() => { cb.current = onText }, [onText])
  useEffect(() => () => rec.current?.abort(), [])

  const toggle = useCallback(() => {
    if (!Recognition) return
    if (rec.current) { rec.current.stop(); return }
    const r = new Recognition()
    r.lang = "fr-FR"
    r.interimResults = false
    r.continuous = false
    r.onresult = (e) => {
      const text = Array.from(e.results).map((x) => x[0].transcript).join(" ").trim()
      if (text) cb.current(text)
    }
    r.onend = () => { rec.current = null; setListening(false) }
    r.onerror = () => { rec.current = null; setListening(false) }
    rec.current = r
    setListening(true)
    r.start()
  }, [])

  return { supported: Boolean(Recognition), listening, toggle }
}
