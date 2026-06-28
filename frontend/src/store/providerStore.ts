import { create } from 'zustand'
import type { ProviderName, ModelInfo } from '../providers/provider'
import { getProvider } from '../hooks/useProvider'
import { useAppStore } from './appStore'

interface ProviderState {
  selectedProvider: ProviderName
  selectedModel: string | null
  models: ModelInfo[]
  isLoadingModels: boolean
  isHealthy: boolean | null
  setProvider: (provider: ProviderName) => void
  setSelectedModel: (model: string | null) => void
  fetchModelsAndCheckHealth: () => Promise<void>
}

export const useProviderStore = create<ProviderState>((set, get) => ({
  selectedProvider: 'liteRT',
  selectedModel: null,
  models: [],
  isLoadingModels: false,
  isHealthy: null,
  setProvider: (provider) => {
    set({ selectedProvider: provider, selectedModel: null, models: [], isHealthy: null })
    get().fetchModelsAndCheckHealth()
  },
  setSelectedModel: (model) => set({ selectedModel: model }),
  fetchModelsAndCheckHealth: async () => {
    const { selectedProvider } = get()
    set({ isLoadingModels: true })
    const providerClient = getProvider(selectedProvider)
    try {
      const isHealthy = await providerClient.health()
      if (isHealthy) {
        const models = await providerClient.listModels()
        const appState = useAppStore.getState()
        const preferredFromSettings =
          appState.defaultProvider === selectedProvider && appState.defaultModel
            ? appState.defaultModel
            : null
        const savedModel = preferredFromSettings ?? window.localStorage.getItem(`model_${selectedProvider}`)
        const activeModel = savedModel && models.some(m => m.id === savedModel)
          ? savedModel
          : (models.length > 0 ? models[0].id : null)

        set({
          isHealthy: true,
          models,
          selectedModel: activeModel,
          isLoadingModels: false
        })
      } else {
        set({ isHealthy: false, models: [], selectedModel: null, isLoadingModels: false })
      }
    } catch (err) {
      console.error('Error al comprobar conexión o cargar modelos:', err)
      set({ isHealthy: false, models: [], selectedModel: null, isLoadingModels: false })
    }
  }
}))
