import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { api } from "../lib/api"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // La session vit dans un cookie httpOnly : on demande simplement à l'API qui est connecté
  useEffect(() => {
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  const authenticate = useCallback(async (path, body) => {
    const { data } = await api.post(path, body)
    setUser(data.user)
    return data.user
  }, [])

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout") } finally { setUser(null) }
  }, [])

  const value = useMemo(() => ({
    user,
    loading,
    login: (email, password) => authenticate("/auth/login", { email, password }),
    register: (name, email, password, extra = {}) => authenticate("/auth/register", { name, email, password, ...extra }),
    resetPassword: (token, password) => authenticate("/auth/reset", { token, password }),
    logout,
  }), [user, loading, authenticate, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
