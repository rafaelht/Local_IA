import { FormEvent, useEffect, useState } from 'react'
import { Card } from '../components/ui/card'
import { useProtectedRoute } from '../hooks/useProtectedRoute'
import {
  useAddFavoriteModel,
  useFavoriteModels,
  usePreferences,
  useRemoveFavoriteModel,
  useUpdatePreferences,
} from '../hooks/usePreferences'
import { useAppStore } from '../store/appStore'
import { useProviderStore } from '../store/providerStore'
import type { ProviderName } from '../providers/provider'

export default function SettingsPage() {
  useProtectedRoute()

  const { data: preferences, isLoading } = usePreferences()
  const { data: favoriteModels = [], isLoading: isLoadingFavorites } = useFavoriteModels()
  const updatePreferences = useUpdatePreferences()
  const addFavoriteModel = useAddFavoriteModel()
  const removeFavoriteModel = useRemoveFavoriteModel()

  const {
    theme,
    devMode,
    temperature,
    contextLength,
    defaultProvider,
    defaultModel,
    setTheme,
    setDevMode,
    setTemperature,
    setContextLength,
    setDefaultProvider,
    setDefaultModel,
  } = useAppStore()

  const { models, selectedProvider, selectedModel, setProvider, setSelectedModel } = useProviderStore()

  const [favoriteProvider, setFavoriteProvider] = useState<ProviderName>('liteRT')
  const [favoriteModelName, setFavoriteModelName] = useState('')
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  useEffect(() => {
    if (preferences) {
      setTheme(preferences.theme)
      setDevMode(preferences.dev_mode)
      setTemperature(preferences.temperature)
      setContextLength(preferences.context_length)
      setDefaultProvider(preferences.default_provider)
      setDefaultModel(preferences.default_model)
    }
  }, [preferences, setTheme, setDevMode, setTemperature, setContextLength, setDefaultProvider, setDefaultModel])

  useEffect(() => {
    setFavoriteProvider(selectedProvider)
    if (selectedModel) {
      setFavoriteModelName(selectedModel)
    }
  }, [selectedProvider, selectedModel])

  const persistPreferences = async (patch: Parameters<typeof updatePreferences.mutateAsync>[0]) => {
    try {
      const updated = await updatePreferences.mutateAsync(patch)
      setTheme(updated.theme)
      setDevMode(updated.dev_mode)
      setTemperature(updated.temperature)
      setContextLength(updated.context_length)
      setDefaultProvider(updated.default_provider)
      setDefaultModel(updated.default_model)
      setSaveMessage('Preferencias guardadas')
      window.setTimeout(() => setSaveMessage(null), 2000)
    } catch (err) {
      console.error('Error al guardar preferencias:', err)
      setSaveMessage('Error al guardar')
      window.setTimeout(() => setSaveMessage(null), 2500)
    }
  }

  const handleAddFavorite = async (e: FormEvent) => {
    e.preventDefault()
    if (!favoriteModelName.trim()) return

    try {
      await addFavoriteModel.mutateAsync({
        provider_name: favoriteProvider,
        model_name: favoriteModelName.trim(),
        temperature,
        context_length: contextLength,
      })
      setSaveMessage('Modelo añadido a favoritos')
      window.setTimeout(() => setSaveMessage(null), 2000)
    } catch (err) {
      console.error('Error al añadir favorito:', err)
    }
  }

  const handleApplyFavorite = async (provider: ProviderName, modelName: string, favTemperature: number, favContextLength: number) => {
    setProvider(provider)
    setSelectedModel(modelName)
    await persistPreferences({
      default_provider: provider,
      default_model: modelName,
      temperature: favTemperature,
      context_length: favContextLength,
    })
  }

  if (isLoading) {
    return (
      <div className="py-16 text-center text-sm text-slate-500">
        Cargando ajustes...
      </div>
    )
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Configuración</p>
          <h1 className="mt-1 text-2xl font-bold text-white">Ajustes y preferencias</h1>
          <p className="mt-2 text-sm text-slate-400">
            Personaliza la apariencia, el comportamiento del chat y tus modelos favoritos.
          </p>
        </div>
        {saveMessage && (
          <span className="rounded-xl border border-cyan-500/30 bg-cyan-950/30 px-3 py-1.5 text-xs font-bold text-cyan-300">
            {saveMessage}
          </span>
        )}
      </div>

      <Card className="space-y-5">
        <div>
          <h2 className="text-lg font-bold text-white">Apariencia</h2>
          <p className="mt-1 text-sm text-slate-400">El tema se aplica de inmediato en toda la aplicación.</p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {(['dark', 'light'] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => persistPreferences({ theme: option })}
              className={`rounded-2xl border px-4 py-3 text-sm font-bold transition ${
                theme === option
                  ? 'border-cyan-500 bg-cyan-950/30 text-cyan-300'
                  : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
              }`}
            >
              {option === 'dark' ? 'Oscuro' : 'Claro'}
            </button>
          ))}
        </div>
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-lg font-bold text-white">Modo desarrollador</h2>
          <p className="mt-1 text-sm text-slate-400">
            Muestra métricas de rendimiento (TTFT, tokens/s, tiempos) durante la generación en el chat.
          </p>
        </div>
        <label className="flex items-center justify-between rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-3">
          <span className="text-sm font-medium text-slate-200">Activar modo desarrollador</span>
          <button
            type="button"
            role="switch"
            aria-checked={devMode}
            onClick={() => persistPreferences({ dev_mode: !devMode })}
            className={`relative h-7 w-12 rounded-full transition ${
              devMode ? 'bg-cyan-500' : 'bg-slate-700'
            }`}
          >
            <span
              className={`absolute top-0.5 h-6 w-6 rounded-full bg-white transition ${
                devMode ? 'left-5' : 'left-0.5'
              }`}
            />
          </button>
        </label>
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-lg font-bold text-white">Generación</h2>
          <p className="mt-1 text-sm text-slate-400">Parámetros por defecto para nuevas conversaciones.</p>
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-slate-300">Temperatura</span>
            <span className="font-mono text-cyan-400">{temperature.toFixed(1)}</span>
          </div>
          <input
            type="range"
            min={0}
            max={2}
            step={0.1}
            value={temperature}
            onChange={(e) => setTemperature(Number(e.target.value))}
            onMouseUp={() => persistPreferences({ temperature })}
            onTouchEnd={() => persistPreferences({ temperature })}
            className="w-full accent-cyan-500"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm text-slate-300" htmlFor="context-length">
            Longitud de contexto
          </label>
          <select
            id="context-length"
            value={contextLength}
            onChange={(e) => {
              const value = Number(e.target.value)
              setContextLength(value)
              persistPreferences({ context_length: value })
            }}
            className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          >
            {[2048, 4096, 8192, 16384, 32768].map((value) => (
              <option key={value} value={value}>
                {value.toLocaleString()} tokens
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-lg font-bold text-white">Proveedor y modelo por defecto</h2>
          <p className="mt-1 text-sm text-slate-400">Se aplicará al iniciar sesión y al abrir el chat.</p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {(['liteRT', 'ollama'] as const).map((provider) => (
            <button
              key={provider}
              type="button"
              onClick={() => {
                setDefaultProvider(provider)
                setProvider(provider)
                persistPreferences({ default_provider: provider, default_model: null })
              }}
              className={`rounded-2xl border px-4 py-3 text-sm font-bold transition ${
                defaultProvider === provider
                  ? 'border-cyan-500 bg-cyan-950/30 text-cyan-300'
                  : 'border-slate-800 bg-slate-950/40 text-slate-400 hover:border-slate-700'
              }`}
            >
              {provider === 'liteRT' ? 'LiteRT-LM' : 'Ollama'}
            </button>
          ))}
        </div>

        {models.length > 0 && (
          <div>
            <label className="mb-2 block text-sm text-slate-300" htmlFor="default-model">
              Modelo por defecto
            </label>
            <select
              id="default-model"
              value={defaultModel ?? selectedModel ?? ''}
              onChange={(e) => {
                const value = e.target.value
                setDefaultModel(value)
                setSelectedModel(value)
                persistPreferences({ default_model: value })
              }}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </Card>

      <Card className="space-y-5">
        <div>
          <h2 className="text-lg font-bold text-white">Modelos favoritos</h2>
          <p className="mt-1 text-sm text-slate-400">
            Acceso rápido a combinaciones proveedor/modelo que uses con frecuencia.
          </p>
        </div>

        <form onSubmit={handleAddFavorite} className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <select
            value={favoriteProvider}
            onChange={(e) => setFavoriteProvider(e.target.value as ProviderName)}
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          >
            <option value="liteRT">LiteRT-LM</option>
            <option value="ollama">Ollama</option>
          </select>
          <input
            type="text"
            value={favoriteModelName}
            onChange={(e) => setFavoriteModelName(e.target.value)}
            placeholder="Nombre del modelo"
            className="rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400"
          />
          <button
            type="submit"
            disabled={addFavoriteModel.isPending || !favoriteModelName.trim()}
            className="rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-bold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50"
          >
            Añadir
          </button>
        </form>

        <div className="space-y-2">
          {isLoadingFavorites ? (
            <p className="text-sm text-slate-500">Cargando favoritos...</p>
          ) : favoriteModels.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-slate-800 px-4 py-6 text-center text-sm text-slate-500">
              No tienes modelos favoritos todavía.
            </p>
          ) : (
            favoriteModels.map((favorite) => (
              <div
                key={favorite.id}
                className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-800 bg-slate-950/50 px-4 py-3"
              >
                <div>
                  <p className="text-sm font-semibold text-white">{favorite.model_name}</p>
                  <p className="text-xs text-slate-500">
                    {favorite.provider_name === 'liteRT' ? 'LiteRT-LM' : 'Ollama'} · T={favorite.temperature} · ctx={favorite.context_length}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      handleApplyFavorite(
                        favorite.provider_name,
                        favorite.model_name,
                        favorite.temperature,
                        favorite.context_length
                      )
                    }
                    className="rounded-xl border border-cyan-500/40 px-3 py-1.5 text-xs font-bold text-cyan-300 transition hover:bg-cyan-950/40"
                  >
                    Usar
                  </button>
                  <button
                    type="button"
                    onClick={() => removeFavoriteModel.mutate(favorite.id)}
                    disabled={removeFavoriteModel.isPending}
                    className="rounded-xl border border-slate-700 px-3 py-1.5 text-xs font-bold text-slate-400 transition hover:border-rose-500/40 hover:text-rose-300"
                  >
                    Quitar
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </Card>
    </section>
  )
}
