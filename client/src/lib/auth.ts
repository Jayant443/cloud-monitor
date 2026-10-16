import { API_BASE_URL } from './api'

export interface AuthUser {
  id: number
  username: string
  email: string
  display_name: string | null
  created_at: string
}

const TOKEN_KEY = 'themonitor_token'

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

export function notifyUnauthorized() {
  unauthorizedHandler?.()
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage unavailable */ }
}

async function authRequest<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const payload = (await response.json()) as { detail?: string | { msg: string }[] }
      if (typeof payload.detail === 'string') detail = payload.detail
      else if (Array.isArray(payload.detail)) detail = payload.detail.map((issue) => issue.msg).join(', ')
    } catch { /* response was not JSON */ }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export interface SignupBody {
  username: string
  email: string
  password: string
  display_name?: string
}

export const authApi = {
  signup: (body: SignupBody) => authRequest<AuthUser>('/api/auth/signup', body),
  login: (identifier: string, password: string) =>
    authRequest<{ access_token: string; token_type: string }>('/api/auth/login', { identifier, password }),
  me: async (signal?: AbortSignal): Promise<AuthUser> => {
    const token = getToken()
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      signal,
      headers: { Accept: 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    })
    if (response.status === 401) notifyUnauthorized()
    if (!response.ok) throw new Error(`Request failed (${response.status})`)
    return response.json() as Promise<AuthUser>
  },
}
