import { api } from "./api"

// Notifications Web Push : abonnement de l'appareil via le service worker (/sw.js)
export const pushSupported = typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window

function keyToBytes(base64url) {
  const pad = "=".repeat((4 - (base64url.length % 4)) % 4)
  const raw = atob((base64url + pad).replace(/-/g, "+").replace(/_/g, "/"))
  return Uint8Array.from(raw, (c) => c.charCodeAt(0))
}

async function registration() {
  return (await navigator.serviceWorker.getRegistration()) || navigator.serviceWorker.register("/sw.js")
}

export async function pushStatus() {
  if (!pushSupported) return "unsupported"
  if (Notification.permission === "denied") return "denied"
  const sub = await (await registration()).pushManager.getSubscription()
  return sub ? "subscribed" : "off"
}

export async function enablePush() {
  const permission = await Notification.requestPermission()
  if (permission !== "granted") throw new Error("Notifications refusées dans le navigateur.")
  const { data } = await api.get("/push/public-key")
  const reg = await registration()
  await navigator.serviceWorker.ready
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyToBytes(data.public_key) })
  const json = sub.toJSON()
  await api.post("/push/subscribe", { endpoint: json.endpoint, keys: json.keys })
}

export async function disablePush() {
  const sub = await (await registration()).pushManager.getSubscription()
  if (!sub) return
  await api.delete("/push/subscribe", { params: { endpoint: sub.endpoint } }).catch(() => {})
  await sub.unsubscribe()
}
