import axios from "axios"

// VITE_API_URL="" (chaîne vide) = même origine que le site (déploiement en un seul service)
export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000"

// Session : cookie httpOnly posé par l'API (envoyé automatiquement, inaccessible au JavaScript)
export const api = axios.create({ baseURL: API_URL, timeout: 45000, withCredentials: true })

/** Message d'erreur lisible à partir d'une erreur axios / FastAPI. */
export function errorMessage(err) {
  const detail = err?.response?.data?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail) && detail.length) {
    const d = detail[0]
    return `${d.loc?.slice(1).join(".") || "Champ"} : ${d.msg}`
  }
  if (err?.code === "ERR_NETWORK") return `API injoignable (${API_URL}). Vérifiez que le backend est lancé.`
  return err?.message || "Erreur inattendue"
}
