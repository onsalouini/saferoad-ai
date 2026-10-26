import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react"
import { api } from "../lib/api"
import { useAuth } from "./AuthContext"

const NotificationContext = createContext(null)
const POLL_MS = 60_000

const supported = typeof window !== "undefined" && "Notification" in window

/** Notifications de l'utilisateur (interrogées chaque minute) + notifications système du navigateur. */
export function NotificationProvider({ children }) {
  const { user } = useAuth()
  const [items, setItems] = useState([])
  const [permission, setPermission] = useState(supported ? Notification.permission : "unsupported")
  const seen = useRef(null)

  const refresh = useCallback(async () => {
    if (!user) return
    try {
      const { data } = await api.get("/notifications")
      setItems(data.items)
      // Notification système pour les nouvelles alertes (pas au premier chargement)
      if (seen.current && supported && Notification.permission === "granted") {
        for (const n of data.items) {
          if (!n.read && !seen.current.has(n.id)) new Notification(n.title, { body: n.message, icon: "/icons/icon-192.png", tag: n.id })
        }
      }
      seen.current = new Set(data.items.map((n) => n.id))
    } catch { /* hors ligne ou session expirée */ }
  }, [user])

  useEffect(() => {
    if (!user) { seen.current = null; return undefined }
    const first = setTimeout(refresh, 0)
    const id = setInterval(refresh, POLL_MS)
    return () => { clearTimeout(first); clearInterval(id) }
  }, [user, refresh])

  const markAllRead = useCallback(async () => {
    await api.post("/notifications/read-all")
    setItems((xs) => xs.map((n) => ({ ...n, read: true })))
  }, [])

  const askPermission = useCallback(async () => {
    if (supported) setPermission(await Notification.requestPermission())
  }, [])

  const value = useMemo(() => ({
    items: user ? items : [],
    unread: user ? items.filter((n) => !n.read).length : 0,
    refresh, markAllRead, permission, askPermission,
  }), [user, items, refresh, markAllRead, permission, askPermission])

  return <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useNotifications() {
  return useContext(NotificationContext)
}
