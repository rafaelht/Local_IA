import { create } from 'zustand'

interface AuthState {
  token: string | null
  userEmail: string | null
  setToken: (token: string | null) => void
  setUserEmail: (email: string | null) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  token: window.localStorage.getItem('auth_token'),
  userEmail: window.localStorage.getItem('auth_user_email'),
  setToken: (token) => {
    if (token) {
      window.localStorage.setItem('auth_token', token)
    } else {
      window.localStorage.removeItem('auth_token')
    }
    set({ token })
  },
  setUserEmail: (userEmail) => {
    if (userEmail) {
      window.localStorage.setItem('auth_user_email', userEmail)
    } else {
      window.localStorage.removeItem('auth_user_email')
    }
    set({ userEmail })
  },
}))
