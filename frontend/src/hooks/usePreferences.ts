import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import { useAuthStore } from '../store/authStore'
import type {
  FavoriteModel,
  FavoriteModelCreate,
  UserPreferences,
  UserPreferencesUpdate,
} from '../types/preferences'

export function usePreferences() {
  const token = useAuthStore((state) => state.token)

  return useQuery<UserPreferences>({
    queryKey: ['preferences'],
    queryFn: async () => {
      const response = await api.get('/api/v1/preferences')
      return response.data
    },
    enabled: Boolean(token),
  })
}

export function useUpdatePreferences() {
  const queryClient = useQueryClient()

  return useMutation<UserPreferences, Error, UserPreferencesUpdate>({
    mutationFn: async (payload) => {
      const response = await api.patch('/api/v1/preferences', payload)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['preferences'], data)
    },
  })
}

export function useFavoriteModels() {
  const token = useAuthStore((state) => state.token)

  return useQuery<FavoriteModel[]>({
    queryKey: ['favorite-models'],
    queryFn: async () => {
      const response = await api.get('/api/v1/preferences/favorite-models')
      return response.data
    },
    enabled: Boolean(token),
  })
}

export function useAddFavoriteModel() {
  const queryClient = useQueryClient()

  return useMutation<FavoriteModel, Error, FavoriteModelCreate>({
    mutationFn: async (payload) => {
      const response = await api.post('/api/v1/preferences/favorite-models', payload)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favorite-models'] })
    },
  })
}

export function useRemoveFavoriteModel() {
  const queryClient = useQueryClient()

  return useMutation<void, Error, number>({
    mutationFn: async (favoriteId) => {
      await api.delete(`/api/v1/preferences/favorite-models/${favoriteId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['favorite-models'] })
    },
  })
}
