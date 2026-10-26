const API_ROOT = '/api'

function cookie(name) {
  return document.cookie.split('; ').find((part) => part.startsWith(`${name}=`))?.split('=')[1]
}

export class ApiError extends Error {
  constructor(payload, status) {
    const flatten = (value) => {
      if (Array.isArray(value)) return value.flatMap(flatten)
      if (value && typeof value === 'object') return Object.values(value).flatMap(flatten)
      return value == null ? [] : [String(value)]
    }
    const messages = flatten(payload?.message)
    const fieldErrors = flatten(payload?.errors)
    super(messages[0] || fieldErrors.join(' ') || 'Request failed')
    this.code = payload?.code || 'REQUEST_FAILED'
    this.errors = payload?.errors
    this.status = status
  }
}

export async function api(path, options = {}, retry = true) {
  const method = options.method || 'GET'
  const headers = new Headers(options.headers || {})
  const csrf = cookie('csrftoken')
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrf) headers.set('X-CSRFToken', decodeURIComponent(csrf))
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers, credentials: 'include' })
  // A 401 from login, registration, password reset, or another auth action
  // is the action's own result. Refreshing an existing session cannot make
  // that request succeed and only creates a second misleading console error.
  const isAuthAction = path.startsWith('/accounts/auth/')
  if (response.status === 401 && retry && !isAuthAction) {
    const refreshed = await fetch(`${API_ROOT}/accounts/auth/refresh/`, { method: 'POST', credentials: 'include' })
    if (refreshed.ok) return api(path, options, false)
  }
  if (response.status === 204) return null
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new ApiError(payload, response.status)
    if (error.code === 'ADMIN_MARKETPLACE_RESTRICTED') {
      window.dispatchEvent(new Event('auth-role-refresh'))
    }
    throw error
  }
  return payload
}

export const get = (path) => api(path)
export const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body || {}) })
export const patch = (path, body) => api(path, { method: 'PATCH', body: JSON.stringify(body || {}) })
export const del = (path) => api(path, { method: 'DELETE' })

export function upload(path, body, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest()
    request.open('POST', `${API_ROOT}${path}`)
    request.withCredentials = true
    const csrf = cookie('csrftoken')
    if (csrf) request.setRequestHeader('X-CSRFToken', decodeURIComponent(csrf))
    request.upload.onprogress = (event) => { if (event.lengthComputable && onProgress) onProgress(Math.round(event.loaded / event.total * 100)) }
    request.onload = () => {
      const payload = (() => { try { return JSON.parse(request.responseText || '{}') } catch { return {} } })()
      if (request.status >= 200 && request.status < 300) resolve(payload)
      else reject(new ApiError(payload, request.status))
    }
    request.onerror = () => reject(new ApiError({ message: 'Upload failed. Check your connection.' }, 0))
    request.send(body)
  })
}
