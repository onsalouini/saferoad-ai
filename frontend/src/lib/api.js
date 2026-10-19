import axios from "axios"

export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000"
export const TOKEN_KEY = "saferoad_token"

export const api = axios.create({ baseURL: API_URL, timeout: 30000 })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

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
