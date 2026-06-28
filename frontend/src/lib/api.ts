import axios from 'axios'
import { getAuthToken } from '../utils/authHelpers'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = getAuthToken()
  if (token) {
    config.headers = config.headers ?? {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// User management
export const createUser = (email: string, password: string, nickname?: string, fullName?: string, role: 'user' | 'admin' = 'user') =>
  api.post('/api/v1/users', { email, password, nickname, full_name: fullName, role })

export const listUsers = () =>
  api.get('/api/v1/users')

export const updateUser = (userId: number, updates: { nickname?: string; full_name?: string; password?: string; is_active?: boolean; role?: string }) =>
  api.put(`/api/v1/users/${userId}`, updates)

export const deleteUser = (userId: number) =>
  api.delete(`/api/v1/users/${userId}`)

export default api
