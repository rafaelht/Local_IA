import { useState, useEffect, useRef } from 'react'
import { Link, Outlet, useNavigate } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { usePreferencesSync } from '../../hooks/usePreferencesSync'
import { useAuthStore } from '../../store/authStore'

export default function AppShell() {
  useTheme()
  usePreferencesSync()

  const token = useAuthStore((state) => state.token)
  const userEmail = useAuthStore((state) => state.userEmail)
  const setToken = useAuthStore((state) => state.setToken)
  const setUserEmail = useAuthStore((state) => state.setUserEmail)
  const navigate = useNavigate()
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  function handleLogout() {
    setToken(null)
    setUserEmail(null)
    setIsUserMenuOpen(false)
    navigate('/login')
  }

  // Close user menu when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false)
      }
    }

    if (isUserMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isUserMenuOpen])

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="fixed top-0 left-0 right-0 z-50 flex h-14 items-center border-b border-slate-700/80 bg-slate-950/95 px-4 backdrop-blur-md">
        <div className="mx-auto flex max-w-full items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Link to="/" className="text-xl font-semibold text-white">
              Local LLM Interface
            </Link>
            <span className="hidden rounded-full border border-slate-700 px-3 py-1 text-xs uppercase tracking-[0.3em] text-slate-500 sm:inline-block">
              Beta
            </span>
          </div>
          <nav className="flex items-center justify-end gap-2 text-sm text-slate-300">
            <Link to="/" className="rounded-2xl px-3 py-2 transition hover:bg-slate-800 hover:text-white">
              Chat
            </Link>
            {token && (
              <Link to="/settings" className="rounded-2xl px-3 py-2 transition hover:bg-slate-800 hover:text-white">
                Ajustes
              </Link>
            )}
            {token ? (
              <div className="relative" ref={userMenuRef}>
                <button
                  type="button"
                  onClick={() => setIsUserMenuOpen((value) => !value)}
                  aria-label="Abrir menu de usuario"
                  aria-expanded={isUserMenuOpen}
                  className="flex h-10 w-10 items-center justify-center rounded-2xl border border-slate-700 bg-slate-900/80 text-sm font-bold text-cyan-300 transition hover:border-cyan-500/40 hover:text-cyan-200"
                >
                  {userEmail?.slice(0, 1).toUpperCase() || 'U'}
                </button>
                {isUserMenuOpen && (
                  <div className="absolute right-0 z-20 mt-2 w-64 overflow-hidden rounded-2xl border border-slate-700 bg-slate-950 shadow-xl shadow-slate-950/50">
                    <div className="border-b border-slate-800 px-4 py-3">
                      <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Sesion</p>
                      <p className="mt-1 truncate text-sm font-medium text-slate-200">{userEmail}</p>
                    </div>
                    <button
                      type="button"
                      onClick={handleLogout}
                      className="block w-full px-4 py-3 text-left text-sm font-medium text-slate-300 transition hover:bg-slate-900 hover:text-white"
                    >
                      Cerrar sesión
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <Link to="/login" className="rounded-2xl px-3 py-2 transition hover:bg-slate-800 hover:text-white">
                Login
              </Link>
            )}
          </nav>
        </div>
      </header>

      <main className="w-full" style={{marginTop: '3.5rem', height: 'calc(100vh - 3.5rem)', overflow: 'hidden'}}>
        <Outlet />
      </main>
    </div>
  )
}
