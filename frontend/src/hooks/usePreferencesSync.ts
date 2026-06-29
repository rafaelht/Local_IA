import { useEffect } from 'react'
import { useAuthStore } from '../store/authStore'
import { useAppStore } from '../store/appStore'
import { useProviderStore } from '../store/providerStore'
import { usePreferences } from './usePreferences'

export function usePreferencesSync() {
  const token = useAuthStore((state) => state.token)
  const hydrateFromPreferences = useAppStore((state) => state.hydrateFromPreferences)
  const markPreferencesLoaded = useAppStore((state) => state.markPreferencesLoaded)
  const setProvider = useProviderStore((state) => state.setProvider)
  const setSelectedModel = useProviderStore((state) => state.setSelectedModel)
  const selectedProvider = useProviderStore((state) => state.selectedProvider)
  const selectedModel = useProviderStore((state) => state.selectedModel)

  const { data: preferences, isSuccess } = usePreferences()

  useEffect(() => {
    if (!token) {
      markPreferencesLoaded()
      return
    }

    if (isSuccess && preferences) {
      hydrateFromPreferences(preferences)
      if (selectedProvider !== preferences.default_provider) {
        setProvider(preferences.default_provider)
      }
      if (preferences.default_model !== selectedModel) {
        setSelectedModel(preferences.default_model)
      }
    }
  }, [
    token,
    isSuccess,
    preferences,
    hydrateFromPreferences,
    markPreferencesLoaded,
    selectedProvider,
    selectedModel,
    setProvider,
    setSelectedModel,
  ])
}
