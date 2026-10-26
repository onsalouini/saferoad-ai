// Service worker SafeRoad AI : l'application s'ouvre hors ligne (coquille en cache).
// Les appels à l'API ne sont jamais mis en cache : les analyses doivent rester à jour.
const CACHE = "saferoad-v3"
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg", "/icons/icon-192.png", "/icons/icon-512.png"]

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()))
})

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  )
})

// Notifications push (alertes de départ), y compris quand l'application est fermée
self.addEventListener("push", (event) => {
  let data = { title: "SafeRoad AI", body: "", url: "/mes-trajets" }
  try { data = { ...data, ...event.data.json() } } catch { /* charge utile non JSON */ }
  event.waitUntil(self.registration.showNotification(data.title, {
    body: data.body, icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", data: { url: data.url },
  }))
})

self.addEventListener("notificationclick", (event) => {
  event.notification.close()
  const url = event.notification.data?.url || "/"
  event.waitUntil(self.clients.matchAll({ type: "window" }).then((wins) => {
    const open = wins.find((w) => new URL(w.url).origin === self.location.origin)
    return open ? open.navigate(url).then((w) => w.focus()) : self.clients.openWindow(url)
  }))
})

self.addEventListener("fetch", (event) => {
  const req = event.request
  const url = new URL(req.url)
  if (req.method !== "GET" || url.origin !== self.location.origin) return

  // Pages : réseau d'abord, coquille en cache si hors ligne
  if (req.mode === "navigate") {
    event.respondWith(fetch(req).catch(() => caches.match("/")))
    return
  }
  // Fichiers statiques (noms versionnés par Vite) : cache d'abord
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        const copy = res.clone()
        if (res.ok) caches.open(CACHE).then((c) => c.put(req, copy))
        return res
      })),
    )
  }
})
