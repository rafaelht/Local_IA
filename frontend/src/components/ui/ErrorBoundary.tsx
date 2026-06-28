import React from 'react'

interface State {
  hasError: boolean
  error?: Error | null
}

class ErrorBoundary extends React.Component<React.PropsWithChildren, State> {
  constructor(props: React.PropsWithChildren) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: any) {
    // TODO: report to telemetry if configured
    // eslint-disable-next-line no-console
    console.error('Uncaught error:', error, info)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null })
    // try a soft reload
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen grid place-items-center p-6">
          <div className="max-w-lg rounded-2xl border border-rose-700 bg-rose-950/60 p-6 text-center">
            <h2 className="text-lg font-bold text-white mb-2">Se ha producido un error inesperado</h2>
            <p className="text-sm text-slate-300 mb-4">Intenta recargar la página o vuelve a intentarlo más tarde.</p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={this.handleReload}
                className="rounded-2xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-900"
              >
                Recargar
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children as React.ReactElement
  }
}

export default ErrorBoundary
