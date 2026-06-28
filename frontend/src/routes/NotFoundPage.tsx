import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] items-center justify-center px-4 py-12">
      <div className="rounded-3xl border border-slate-700 bg-slate-900/80 p-8 text-center max-w-md w-full">
        <h1 className="text-3xl font-semibold text-white">404</h1>
        <p className="mt-4 text-slate-400">Página no encontrada.</p>
        <Link to="/" className="mt-6 inline-flex rounded-2xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-400">
          Volver al chat
        </Link>
      </div>
    </div>
  )
}
