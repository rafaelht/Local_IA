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

  const { data: preferences, isSuccess } = usePreferences()

  useEffect(() => {
    if (!token) {
      markPreferencesLoaded()
      return
    }

    if (isSuccess && preferences) {
      hydrateFromPreferences(preferences)
      setProvider(preferences.default_provider)
      if (preferences.default_model) {
        setSelectedModel(preferences.default_model)
      }
    }
  }, [
    token,
    isSuccess,
    preferences,
    hydrateFromPreferences,
    markPreferencesLoaded,
    setProvider,
    setSelectedModel,
  ])
}
