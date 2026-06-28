import { create } from 'zustand'
import type { ProviderName } from '../providers/provider'
import type { UserPreferences } from '../types/preferences'

interface AppState {
  theme: 'dark' | 'light'
  devMode: boolean
  temperature: number
  contextLength: number
  defaultProvider: ProviderName
  defaultModel: string | null
  preferencesLoaded: boolean
  setTheme: (theme: 'dark' | 'light') => void
  setDevMode: (devMode: boolean) => void
  setTemperature: (temperature: number) => void
  setContextLength: (contextLength: number) => void
  setDefaultProvider: (provider: ProviderName) => void
  setDefaultModel: (model: string | null) => void
  hydrateFromPreferences: (preferences: UserPreferences) => void
  markPreferencesLoaded: () => void
}

const readStoredTheme = (): 'dark' | 'light' => {
  const stored = window.localStorage.getItem('theme')
  return stored === 'light' ? 'light' : 'dark'
}

export const useAppStore = create<AppState>((set) => ({
  theme: readStoredTheme(),
  devMode: window.localStorage.getItem('dev_mode') === 'true',
  temperature: 0.7,
  contextLength: 2048,
  defaultProvider: 'liteRT',
  defaultModel: null,
  preferencesLoaded: false,
  setTheme: (theme) => {
    window.localStorage.setItem('theme', theme)
    set({ theme })
  },
  setDevMode: (devMode) => {
    window.localStorage.setItem('dev_mode', String(devMode))
    set({ devMode })
  },
  setTemperature: (temperature) => set({ temperature }),
  setContextLength: (contextLength) => set({ contextLength }),
  setDefaultProvider: (defaultProvider) => set({ defaultProvider }),
  setDefaultModel: (defaultModel) => set({ defaultModel }),
  hydrateFromPreferences: (preferences) => {
    window.localStorage.setItem('theme', preferences.theme)
    window.localStorage.setItem('dev_mode', String(preferences.dev_mode))
    set({
      theme: preferences.theme,
      devMode: preferences.dev_mode,
      temperature: preferences.temperature,
      contextLength: preferences.context_length,
      defaultProvider: preferences.default_provider,
      defaultModel: preferences.default_model,
      preferencesLoaded: true,
    })
  },
  markPreferencesLoaded: () => set({ preferencesLoaded: true }),
}))
