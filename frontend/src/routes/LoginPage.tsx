import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'

export default function LoginPage() {
  const [email, setEmail] = useState('admin@local')
  const [password, setPassword] = useState('admin123')
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const setToken = useAuthStore((state) => state.setToken)
  const setUserEmail = useAuthStore((state) => state.setUserEmail)
  const token = useAuthStore((state) => state.token)

  useEffect(() => {
    if (token) {
      navigate('/')
    }
  }, [navigate, token])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)

    try {
      const response = await api.post('/api/v1/auth/login', { email, password })
      const { access_token } = response.data
      setToken(access_token)
      setUserEmail(email)
      navigate('/')
    } catch (err) {
      setError('Correo o contraseña incorrectos. Intenta de nuevo.')
    }
  }

  return (
    <section className="mx-auto max-w-2xl rounded-3xl border border-slate-700 bg-slate-900/70 p-8 shadow-xl shadow-slate-950/30">
      <h1 className="text-3xl font-semibold text-white">Acceso</h1>
      <p className="mt-3 text-slate-400">Inicia sesión para usar la interfaz y mantener tu historial de chat.</p>
      <form onSubmit={handleSubmit} className="mt-8 space-y-4">
        {error ? <div className="rounded-2xl bg-rose-500/10 p-4 text-sm text-rose-200">{error}</div> : null}

        <label className="block text-sm font-medium text-slate-200">Email</label>
        <input
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none focus:border-cyan-400"
          placeholder="usuario@ejemplo.com"
          type="email"
          required
        />

        <label className="block text-sm font-medium text-slate-200">Contraseña</label>
        <input
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          type="password"
          className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-white outline-none focus:border-cyan-400"
          placeholder="••••••••"
          required
        />

        <button
          type="submit"
          className="w-full rounded-2xl bg-cyan-500 px-4 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400"
        >
          Iniciar sesión
        </button>
      </form>
    </section>
  )
}
