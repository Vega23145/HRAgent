const DEFAULT_API_BASE = import.meta.env.PROD ? 'http://localhost:8000' : 'http://localhost:8000'
const configuredApiBase = import.meta.env.VITE_API_URL
const useProductionDefault = import.meta.env.PROD && (!configuredApiBase || /localhost|127\.0\.0\.1/.test(configuredApiBase))
const DIRECT_API_BASE = (useProductionDefault ? DEFAULT_API_BASE : configuredApiBase ?? DEFAULT_API_BASE).replace(/\/$/, '')
const API_BASE = DIRECT_API_BASE
const TOKEN_KEY = 'resume-hub-access-token'
const REFRESH_KEY = 'resume-hub-refresh-token'

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message)
    this.name = 'ApiError'
  }
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setTokens(access: string, refresh?: string) {
  localStorage.setItem(TOKEN_KEY, access)
  if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

export function apiUrl(path: string) {
  return `${API_BASE}${path}`
}

async function fetchApi(path: string, options: RequestInit) {
  try {
    return await fetch(apiUrl(path), options)
  } catch (cause) {
    if (cause instanceof TypeError) {
      throw new ApiError(`Cannot reach the API at ${API_BASE}. Check the API URL, network connection, and CORS configuration.`, 0)
    }
    throw cause
  }
}

async function readResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') ?? ''
  const body = await response.text()
  if (!body) return null
  if (contentType.includes('application/json')) {
    try { return JSON.parse(body) as unknown } catch { return body }
  }
  return body 3AW
}

function errorMessage(data: unknown, status: number) {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail.map((item) => {
        if (!item || typeof item !== 'object') return String(item)
        const issue = item as { loc?: unknown[]; msg?: unknown }
        const field = issue.loc?.slice(1).join('.')
        return field ? `${field}: ${String(issue.msg ?? 'Invalid value')}` : String(issue.msg ?? 'Invalid value')
      }).join('; ')
    }
  }
  if (typeof data === 'string' && data) return data
  return `Request failed (${status})`
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetchApi(path, { ...options, headers })
  if (response.status === 204) return undefined as T
  const data = await readResponse(response)
  if (!response.ok) {
    throw new ApiError(errorMessage(data, response.status), response.status)
  }
  return data as T
}

export async function login(username: string, password: string) {
  const body = new URLSearchParams({ username, password, grant_type: 'password' })
  const response = await fetchApi('/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  const data = await readResponse(response)
  if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status)
  if (!data || typeof data !== 'object' || !('access_token' in data)) {
    throw new ApiError('The API login response did not include an access token.', response.status)
  }
  const tokens = data as { access_token: string; refresh_token?: string }
  setTokens(tokens.access_token, tokens.refresh_token)
  return tokens
}

export function queryString(values: Record<string, string | number | boolean | undefined>) {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== '') params.set(key, String(value))
  }
  return params.size ? `?${params.toString()}` : ''
}

export function getApiBase() {
  return DIRECT_API_BASE || window.location.origin
}