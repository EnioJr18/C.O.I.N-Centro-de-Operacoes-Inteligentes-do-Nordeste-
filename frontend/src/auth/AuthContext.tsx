import { createContext, useCallback, useContext, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { ApiClient } from '../api/client'
import type { User } from '../api/types'

interface AuthContextValue { user: User | null; client: ApiClient; login: (email: string, password: string) => Promise<void>; logout: () => void }
const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const client = useRef<ApiClient | null>(null)
  if (!client.current) client.current = new ApiClient(() => setUser(null))
  const api = client.current
  const logout = useCallback(() => { api.clear(); setUser(null) }, [api])
  const login = useCallback(async (email: string, password: string) => { setUser(await api.login(email, password)) }, [api])
  return <AuthContext.Provider value={{ user, client: api, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('AuthProvider ausente.')
  return value
}
