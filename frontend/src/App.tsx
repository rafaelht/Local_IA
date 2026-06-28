import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import AppShell from './components/layout/AppShell'

const ChatPage = lazy(() => import('./routes/ChatPage'))
const LoginPage = lazy(() => import('./routes/LoginPage'))
const SettingsPage = lazy(() => import('./routes/SettingsPage'))
const NotFoundPage = lazy(() => import('./routes/NotFoundPage'))

function App() {
  return (
    <Suspense fallback={<div className="min-h-screen grid place-items-center text-slate-400">Cargando...</div>}>
      <Routes>
        <Route path="/" element={<AppShell />}>
          <Route index element={<ChatPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="login" element={<LoginPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
