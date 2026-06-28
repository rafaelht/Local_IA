import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../lib/api'
import type { Conversation, Message } from '../types/conversation'

// Get all conversations with optional search filter
export function useConversations(search?: string) {
  return useQuery<Conversation[], Error>({
    queryKey: ['conversations', search],
    queryFn: async (): Promise<Conversation[]> => {
      const response = await api.get('/api/v1/conversations', {
        params: search ? { search } : undefined,
      })
      return response.data
    },
    staleTime: 10000,
    gcTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  })
}

// Get a single conversation with details (messages)
export function useConversation(id?: number) {
  return useQuery<Conversation, Error>({
    queryKey: ['conversation', id],
    queryFn: async (): Promise<Conversation> => {
      if (!id) throw new Error('ID no proporcionado')
      const response = await api.get(`/api/v1/conversations/${id}`)
      return response.data
    },
    enabled: !!id,
    staleTime: 10000,
    gcTime: 1000 * 60 * 5,
    refetchOnWindowFocus: false,
  })
}

// Create a new conversation
export function useCreateConversation() {
  const queryClient = useQueryClient()
  return useMutation<Conversation, Error, { title?: string }>({
    mutationFn: async (data) => {
      const response = await api.post('/api/v1/conversations', data)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
    }
  })
}

// Update a conversation (rename, pin, favorite)
export function useUpdateConversation() {
  const queryClient = useQueryClient()
  return useMutation<Conversation, Error, { id: number; title?: string; pinned?: boolean; favorite?: boolean }>({
    mutationFn: async ({ id, ...data }) => {
      const response = await api.put(`/api/v1/conversations/${id}`, data)
      return response.data
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', data.id] })
    }
  })
}

// Delete a conversation
export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, number>({
    mutationFn: async (id) => {
      await api.delete(`/api/v1/conversations/${id}`)
    },
    onSuccess: (_, id) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', id] })
    }
  })
}

// Add a message
export function useAddMessage() {
  const queryClient = useQueryClient()
  return useMutation<Message, Error, { conversationId: number; role: string; content: string }>({
    mutationFn: async ({ conversationId, role, content }) => {
      const response = await api.post(`/api/v1/conversations/${conversationId}/messages`, { role, content })
      return response.data
    },
    onSuccess: (_, { conversationId }) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] })
    }
  })
}

// Delete a message
export function useDeleteMessage() {
  const queryClient = useQueryClient()
  return useMutation<void, Error, { conversationId: number; messageId: number }>({
    mutationFn: async ({ conversationId, messageId }) => {
      await api.delete(`/api/v1/conversations/${conversationId}/messages/${messageId}`)
    },
    onSuccess: (_, { conversationId }) => {
      queryClient.invalidateQueries({ queryKey: ['conversations'] })
      queryClient.invalidateQueries({ queryKey: ['conversation', conversationId] })
    }
  })
}
