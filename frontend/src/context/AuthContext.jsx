import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { api, TOKEN_KEY } from "../lib/api"

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => Boolean(localStorage.getItem(TOKEN_KEY)))

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) return
    api.get("/auth/me")
      .then((r) => setUser(r.data))
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  const authenticate = useCallback(async (path, body) => {
    const { data } = await api.post(path, body)
    localStorage.setItem(TOKEN_KEY, data.token)
    setUser(data.user)
    return data.user
  }, [])

  const value = useMemo(() => ({
    user,
    loading,
    login: (email, password) => authenticate("/auth/login", { email, password }),
    register: (name, email, password) => authenticate("/auth/register", { name, email, password }),
    logout: () => { localStorage.removeItem(TOKEN_KEY); setUser(null) },
  }), [user, loading, authenticate])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  return useContext(AuthContext)
}
