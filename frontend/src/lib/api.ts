import axios from 'axios'
import { getAuthToken } from '../utils/authHelpers'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://10.0.0.84:8001',
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

export default api
