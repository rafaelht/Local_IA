export function getAuthToken(): string | null {
  return window.localStorage.getItem('auth_token')
}

export function setAuthToken(token: string | null) {
  if (token) {
    window.localStorage.setItem('auth_token', token)
  } else {
    window.localStorage.removeItem('auth_token')
  }
}

export function clearAuth() {
  window.localStorage.removeItem('auth_token')
  window.localStorage.removeItem('auth_user_email')
}
