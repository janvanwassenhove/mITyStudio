const BASE = '/api'

export class ApiError extends Error {
  status: number
  detail: unknown
  constructor(status: number, detail: unknown) {
    super(`API error ${status}: ${JSON.stringify(detail)}`)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(BASE + path, {
    method,
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail: unknown
    try { detail = (await res.json()).detail } catch { detail = res.statusText }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
  /** Upload a file via multipart form data. */
  async upload<T>(path: string, file: Blob, filename: string, fields?: Record<string, string>): Promise<T> {
    const form = new FormData()
    form.append('file', file, filename)
    for (const [k, v] of Object.entries(fields ?? {})) form.append(k, v)
    const res = await fetch(BASE + path, { method: 'POST', body: form })
    if (!res.ok) {
      let detail: unknown
      try { detail = (await res.json()).detail } catch { detail = res.statusText }
      throw new ApiError(res.status, detail)
    }
    return res.json() as Promise<T>
  },
}

export interface HealthResponse {
  status: string
  root: string
  capabilities: { fluidsynth: boolean; ffmpeg: boolean; voice_clone?: boolean }
}

export const getHealth = () => api.get<HealthResponse>('/health')

export interface VersionResponse {
  app_version: string
  backend_build: string
  python: string
  engines: { instrument: string; vocal: string }
  capabilities: { fluidsynth: boolean; ffmpeg: boolean; voice_clone?: boolean }
  singing_engine: {
    svs_runtime: boolean
    vocoder_installed: boolean
    voicebanks: string[]
    voicebank_problems: Record<string, string>
  }
}

export const getVersion = () => api.get<VersionResponse>('/version')
