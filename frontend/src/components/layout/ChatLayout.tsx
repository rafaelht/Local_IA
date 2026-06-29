import { memo, useCallback, useEffect, useMemo, useRef, useState, FormEvent, KeyboardEvent } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import api from '../../lib/api'
import { Card } from '../ui/card'
import {
  useConversations,
  useConversation,
  useCreateConversation,
  useUpdateConversation,
  useDeleteConversation,
  useDeleteMessage,
} from '../../hooks/useConversations'
import { useProviderStore } from '../../store/providerStore'
import { useAppStore } from '../../store/appStore'
import { getAuthToken } from '../../utils/authHelpers'
import { MessageBubble } from '../chat/MessageBubble'
import Skeleton from '../ui/Skeleton'
import { useRafState } from '../../hooks/useRafState'
import type { ChatAttachment } from '../../providers/provider'
import type { Conversation, Message } from '../../types/conversation'

// Debounce hook to optimize database search queries
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value)

  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedValue(value)
    }, delay)

    return () => {
      clearTimeout(handler)
    }
  }, [value, delay])

  return debouncedValue
}

interface Metrics {
  providerName: string
  modelName: string
  ttft: number | null
  generationTime: number | null
  tokensPerSec: number | null
  inputTokens: number
  outputTokens: number
  dbQueryMs?: number | null
  dbWriteMs?: number | null
  contextBuildMs?: number | null
  tokenCountMs?: number | null
  modelCallMs?: number | null
  prefillMs?: number | null
  selectedMessageCount?: number | null
  totalMessageCount?: number | null
  totalHistoryTokens?: number | null
  contextBudgetTokens?: number | null
  responseTokenReserve?: number | null
  summaryUsed?: boolean
  summaryGenerationMs?: number | null
  cacheHit?: boolean
}

interface BackendMetricsEvent {
  type: 'metrics'
  phase: 'context_ready' | 'completed'
  metrics: {
    db_query_ms?: number
    db_write_ms?: number
    context_build_ms?: number
    token_count_ms?: number
    model_call_ms?: number
    prefill_ms?: number
    ttft_ms?: number
    generation_tokens_per_sec?: number
    input_tokens?: number
    output_tokens?: number
    selected_message_count?: number
    total_message_count?: number
    total_history_tokens?: number
    context_budget_tokens?: number
    response_token_reserve?: number
    summary_used?: boolean
    summary_generation_ms?: number
    cache_hit?: boolean
  }
}

type PendingAttachment = ChatAttachment & { id: string }

function createConversationTitle(prompt: string): string {
  const stopWords = new Set([
    'a',
    'al',
    'con',
    'como',
    'de',
    'del',
    'el',
    'en',
    'la',
    'las',
    'los',
    'para',
    'por',
    'que',
    'quiero',
    'un',
    'una',
    'y',
  ])

  const words = prompt
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .split(/\s+/)
    .map((word) => word.trim())
    .filter((word) => word.length > 1 && !stopWords.has(word.toLowerCase()))
    .slice(0, 6)

  const title = words.join(' ').trim()
  if (!title) return 'Chat sin titulo'

  return title.length > 60 ? `${title.slice(0, 57).trim()}...` : title
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatDuration(durationMs: number): string {
  const seconds = Math.round(durationMs / 1000)
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`
  }
  return `${(durationMs / 1000).toFixed(2)} s`
}

function getMessageMetricKey(conversationId: number, messageId: number): string {
  return `${conversationId}:${messageId}`
}

function isTextFile(file: File): boolean {
  return (
    file.type.startsWith('text/') ||
    [
      'application/json',
      'application/xml',
      'application/javascript',
      'application/typescript',
      'text/markdown',
      'text/csv',

    ].includes(file.type) ||
    /\.(md|txt|csv|json|xml|log|js|ts|tsx|jsx|py|html|css|yaml|yml)$/i.test(file.name)
  )
}

function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

function buildChatContent(prompt: string, attachments: ChatAttachment[]): string | any[] {
  if (attachments.length === 0) return prompt

  const content: any[] = [{ type: 'text', text: prompt }]

  for (const attachment of attachments) {
    if (attachment.kind === 'image' && attachment.dataUrl) {
      // attachment.dataUrl is already data:image/...;base64,...
      content.push({
        type: 'image_url',
        image_url: { url: attachment.dataUrl }
      })
    } else if (attachment.kind === 'text' && attachment.content) {
      content[0].text += `\n\nArchivo: ${attachment.name}\nTipo: ${attachment.type || 'texto'}\nContenido:\n${attachment.content.slice(0, 12000)}`
    } else {
      content[0].text += `\n\nArchivo adjunto: ${attachment.name} (${attachment.type || 'archivo'}, ${formatFileSize(attachment.size)}). No se pudo extraer su contenido en el navegador.`
    }
  }

  return content
}

function appendAttachmentSummary(prompt: string, attachments: ChatAttachment[]): string {
  if (attachments.length === 0) return prompt
  return `${prompt}\n\nAdjuntos: ${attachments.map((attachment) => attachment.name).join(', ')}`
}

export default function ChatLayout() {
  const [searchVal, setSearchVal] = useState('')
  const searchDebounced = useDebounce(searchVal, 300)

  const [activeId, setActiveId] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [inputText, setInputText] = useState('')
  const [attachments, setAttachments] = useState<PendingAttachment[]>([])
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [showConversations, setShowConversations] = useState(() => {
    const stored = window.localStorage.getItem('showConversations')
    if (stored !== null) {
      return stored === 'true'
    }
    // Default: show on large screens, hide on mobile
    return window.matchMedia('(min-width: 1024px)').matches
  })

  // Streaming & Metrics State
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent, resetStreamingContent] = useRafState('')
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)
  const [lastMetrics, setLastMetrics, resetLastMetrics] = useRafState<Metrics | null>(null)
  const [messageMetrics, setMessageMetrics] = useState<Record<string, Metrics>>({})

  // Queries & Mutations
  const { data: conversations = [], isLoading: isLoadingList } = useConversations(searchDebounced)
  const { data: activeConversation, isLoading: isLoadingConversation } = useConversation(activeId ?? undefined)

  const createMutation = useCreateConversation()
  const updateMutation = useUpdateConversation()
  const deleteMutation = useDeleteConversation()
  const deleteMessageMutation = useDeleteMessage()
  const queryClient = useQueryClient()

  // App / Settings Store
  const { devMode, temperature, contextLength, enableContextHistory } = useAppStore()

  // Provider Store
  const {
    selectedProvider,
    selectedModel,
    fetchModelsAndCheckHealth,
  } = useProviderStore()

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const chatControllerRef = useRef<AbortController | null>(null)
  const wasStreamingRef = useRef(false)
  const pendingStreamingBufferRef = useRef('')
  const streamingFlushRef = useRef<number | null>(null)

  const scheduleStreamingFlush = useCallback(() => {
    if (streamingFlushRef.current !== null) return

    const flushStep = () => {
      const pending = pendingStreamingBufferRef.current
      if (!pending) {
        streamingFlushRef.current = null
        return
      }

      const chunkSize = Math.min(4, Math.max(1, Math.ceil(pending.length / 20)))
      const nextChunk = pending.slice(0, chunkSize)
      pendingStreamingBufferRef.current = pending.slice(chunkSize)
      setStreamingContent((current) => current + nextChunk)

      if (pendingStreamingBufferRef.current.length > 0) {
        streamingFlushRef.current = requestAnimationFrame(flushStep)
      } else {
        streamingFlushRef.current = null
      }
    }

    streamingFlushRef.current = requestAnimationFrame(flushStep)
  }, [setStreamingContent])

  // Simple sanitizer for display purposes: strip common JSX attribute fragments
  const sanitizeTitleForDisplay = (raw: string | undefined) => {
    if (!raw) return ''
    return raw
      .replace(/aria-label="[^"]*"/g, '')
      .replace(/className="[^"]*"/g, '')
      .replace(/\s{2,}/g, ' ')
      .trim()
  }

  const selectedProviderLabel = useMemo(
    () => (selectedProvider === 'liteRT' ? 'LiteRT-LM' : 'Ollama'),
    [selectedProvider]
  )

  const selectedModelValue = selectedModel ?? 'default'

  // Fetch models and test connection on mount
  useEffect(() => {
    fetchModelsAndCheckHealth()
  }, [])

  // Scroll to bottom only when streaming (new content being generated)
  useEffect(() => {
    if (streamingContent) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
    }
  }, [streamingContent])

  useEffect(() => {
    if (wasStreamingRef.current && !isStreaming) {
      inputRef.current?.focus()
    }
    wasStreamingRef.current = isStreaming
  }, [isStreaming])

  useEffect(() => {
    window.localStorage.setItem('showConversations', String(showConversations))
  }, [showConversations])

  // Select the first conversation on list load if none selected and not searching
  useEffect(() => {
    if (conversations.length > 0 && activeId === null && !searchDebounced) {
      setActiveId(conversations[0].id)
    }
  }, [conversations, activeId, searchDebounced])

  const handleCreate = useCallback(async () => {
    try {
      const newChat = await createMutation.mutateAsync({ title: 'Nueva conversación' })
      setActiveId(newChat.id)
    } catch (err) {
      console.error('Error al crear conversación:', err)
    }
  }, [createMutation])

  const handleRename = useCallback(
    async (id: number) => {
      if (!editTitle.trim()) {
        setEditingId(null)
        return
      }
      try {
        await updateMutation.mutateAsync({ id, title: editTitle.trim() })
        setEditingId(null)
      } catch (err) {
        console.error('Error al renombrar:', err)
      }
    },
    [editTitle, updateMutation]
  )

  const handleTogglePin = useCallback(
    async (id: number, currentPinned: boolean) => {
      try {
        await updateMutation.mutateAsync({ id, pinned: !currentPinned })
      } catch (err) {
        console.error('Error al cambiar pin:', err)
      }
    },
    [updateMutation]
  )

  const handleDelete = useCallback(
    async (id: number) => {
      setDeleteConfirmId(id)
    },
    []
  )

  const confirmDelete = useCallback(
    async () => {
      if (deleteConfirmId === null) return
      setDeletingId(deleteConfirmId)
      try {
        await deleteMutation.mutateAsync(deleteConfirmId)
        if (activeId === deleteConfirmId) {
          setActiveId(null)
        }
        setDeleteConfirmId(null)
      } catch (err) {
        console.error('Error al eliminar:', err)
        setDeleteConfirmId(null)
      } finally {
        setDeletingId(null)
      }
    },
    [deleteConfirmId, activeId, deleteMutation]
  )

  const handleStop = useCallback(() => {
    try {
      if (chatControllerRef.current) {
        chatControllerRef.current.abort()
        chatControllerRef.current = null
      }
    } catch (err) {
      console.error('Error al detener la generación:', err)
    }
  }, [])

  const handleAttachFiles = useCallback(async (files: FileList | null) => {
    if (!files || files.length === 0) return

    const maxFileSize = 8 * 1024 * 1024
    const nextAttachments: PendingAttachment[] = []

    for (const file of Array.from(files)) {
      if (file.size > maxFileSize) {
        window.alert(`${file.name} supera el limite de 8 MB.`)
        continue
      }

      try {
        const id = `${file.name}-${file.size}-${file.lastModified}`
        if (file.type.startsWith('image/')) {
          nextAttachments.push({
            id,
            name: file.name,
            type: file.type,
            size: file.size,
            kind: 'image',
            dataUrl: await readFileAsDataUrl(file),
          })
        } else if (isTextFile(file)) {
          nextAttachments.push({
            id,
            name: file.name,
            type: file.type,
            size: file.size,
            kind: 'text',
            content: await readFileAsText(file),
          })
        } else {
          nextAttachments.push({
            id,
            name: file.name,
            type: file.type,
            size: file.size,
            kind: 'binary',
          })
        }
      } catch (err) {
        console.error('Error al leer archivo:', err)
        window.alert(`No se pudo leer ${file.name}.`)
      }
    }

    setAttachments((current) => [...current, ...nextAttachments].slice(0, 6))
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }, [])

  const handleSendMessage = useCallback(
    async (e: FormEvent | null, retryText?: string) => {
      if (e) e.preventDefault()
      if (isStreaming || !activeId) return

      const userText = retryText || inputText.trim()
      const attachmentsForSend = retryText ? [] : attachments
      if (!userText && attachmentsForSend.length === 0) return
      if (!retryText) {
        setInputText('')
        setAttachments([])
      }
      const currentConversation = activeConversation ?? conversations.find((chat) => chat.id === activeId)
      const shouldAutoTitle =
        !retryText &&
        currentConversation?.messages.length === 0 &&
        currentConversation.title.trim().toLowerCase() === 'nueva conversación'
      const promptForModel = buildChatContent(userText, attachmentsForSend)
      const userContentForHistory = appendAttachmentSummary(userText || 'Revisa los archivos adjuntos.', attachmentsForSend)

      setPendingUserMessage(userContentForHistory)

      // 1. Set streaming states and initial metrics
      if (streamingFlushRef.current !== null) {
        cancelAnimationFrame(streamingFlushRef.current)
        streamingFlushRef.current = null
      }
      pendingStreamingBufferRef.current = ''
      setIsStreaming(true)
      resetStreamingContent('')

      const currentMetrics: Metrics = {
        providerName: selectedProviderLabel,
        modelName: selectedModelValue,
        ttft: null,
        generationTime: null,
        tokensPerSec: null,
        inputTokens: Math.ceil(promptForModel.length / 4),
        outputTokens: 0,
      }
      setLastMetrics(currentMetrics)

      const startTime = performance.now()
      let firstTokenReceived = false
      let tokenCount = 0
      let accumulatedText = ''

      chatControllerRef.current = new AbortController()
      const token = getAuthToken()
      const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || ''
      const chatUrl = `${apiBaseUrl}/api/v1/conversations/${activeId}/chat`

      try {
        const response = await fetch(chatUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            role: 'user',
            content: promptForModel,  // Can be string or array with images
            provider: selectedProvider,
            model: selectedModelValue,
            temperature,
            max_tokens: contextLength,
            enable_context_history: enableContextHistory,
          }),
          signal: chatControllerRef.current.signal,
        })

        if (!response.ok) {
          throw new Error(`Error del servidor: ${response.status} ${response.statusText}`)
        }

        const reader = response.body?.getReader()
        if (!reader) {
          throw new Error('El servidor no retornó un stream legible')
        }

        const decoder = new TextDecoder('utf-8')
        let buffer = ''
        let currentEvent = 'message'
        let currentDataLines: string[] = []

        const flushSseEvent = () => {
          if (currentDataLines.length === 0) {
            currentEvent = 'message'
            return
          }

          const payloadText = currentDataLines.join('\n').trim()
          currentDataLines = []

          if (!payloadText || payloadText === '[DONE]') {
            currentEvent = 'message'
            return
          }

          try {
            const parsed = JSON.parse(payloadText)

            if (currentEvent === 'metrics' && parsed.type === 'metrics') {
              const metricsEvent = parsed as BackendMetricsEvent
              currentMetrics.dbQueryMs = metricsEvent.metrics.db_query_ms ?? currentMetrics.dbQueryMs ?? null
              currentMetrics.dbWriteMs = metricsEvent.metrics.db_write_ms ?? currentMetrics.dbWriteMs ?? null
              currentMetrics.contextBuildMs = metricsEvent.metrics.context_build_ms ?? currentMetrics.contextBuildMs ?? null
              currentMetrics.tokenCountMs = metricsEvent.metrics.token_count_ms ?? currentMetrics.tokenCountMs ?? null
              currentMetrics.modelCallMs = metricsEvent.metrics.model_call_ms ?? currentMetrics.modelCallMs ?? null
              currentMetrics.prefillMs = metricsEvent.metrics.prefill_ms ?? currentMetrics.prefillMs ?? null
              currentMetrics.ttft = metricsEvent.metrics.ttft_ms ?? currentMetrics.ttft
              currentMetrics.tokensPerSec = metricsEvent.metrics.generation_tokens_per_sec ?? currentMetrics.tokensPerSec
              currentMetrics.inputTokens = metricsEvent.metrics.input_tokens ?? currentMetrics.inputTokens
              currentMetrics.outputTokens = metricsEvent.metrics.output_tokens ?? currentMetrics.outputTokens
              currentMetrics.selectedMessageCount = metricsEvent.metrics.selected_message_count ?? currentMetrics.selectedMessageCount ?? null
              currentMetrics.totalMessageCount = metricsEvent.metrics.total_message_count ?? currentMetrics.totalMessageCount ?? null
              currentMetrics.totalHistoryTokens = metricsEvent.metrics.total_history_tokens ?? currentMetrics.totalHistoryTokens ?? null
              currentMetrics.contextBudgetTokens = metricsEvent.metrics.context_budget_tokens ?? currentMetrics.contextBudgetTokens ?? null
              currentMetrics.responseTokenReserve = metricsEvent.metrics.response_token_reserve ?? currentMetrics.responseTokenReserve ?? null
              currentMetrics.summaryUsed = metricsEvent.metrics.summary_used ?? currentMetrics.summaryUsed ?? false
              currentMetrics.summaryGenerationMs = metricsEvent.metrics.summary_generation_ms ?? currentMetrics.summaryGenerationMs ?? null
              currentMetrics.cacheHit = metricsEvent.metrics.cache_hit ?? currentMetrics.cacheHit ?? false
              if (metricsEvent.phase === 'completed' && currentMetrics.modelCallMs !== null && currentMetrics.modelCallMs !== undefined) {
                currentMetrics.generationTime = Math.round(currentMetrics.modelCallMs)
              }
              setLastMetrics({ ...currentMetrics })
              currentEvent = 'message'
              return
            }

            const chunk = parsed.choices?.[0]?.delta?.content || ''
            if (!chunk) {
              currentEvent = 'message'
              return
            }

            if (!firstTokenReceived) {
              firstTokenReceived = true
              currentMetrics.ttft = currentMetrics.ttft ?? Math.round(performance.now() - startTime)
            }

            accumulatedText += chunk
            pendingStreamingBufferRef.current += chunk
            scheduleStreamingFlush()
            tokenCount += Math.max(1, Math.ceil(chunk.length / 4))

            const elapsedSecs = (performance.now() - startTime) / 1000
            currentMetrics.tokensPerSec = elapsedSecs > 0 ? Math.round(tokenCount / elapsedSecs) : 0
            currentMetrics.outputTokens = tokenCount
            setLastMetrics({ ...currentMetrics })
          } catch (err) {
            console.error('Error al parsear evento SSE:', err, 'Payload:', payloadText)
          } finally {
            currentEvent = 'message'
          }
        }

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() || ''

          for (const line of lines) {
              const cleanLine = line.replace(/\r$/, '')
              if (!cleanLine.trim()) {
                flushSseEvent()
                continue
              }
              if (cleanLine.startsWith('event:')) {
                currentEvent = cleanLine.substring(6).trim() || 'message'
                continue
              }
              if (cleanLine.startsWith('data:')) {
                currentDataLines.push(cleanLine.substring(5).trimStart())
              }
          }
        }

          flushSseEvent()

        const endTime = performance.now()
        const duration = endTime - startTime
          currentMetrics.generationTime = currentMetrics.generationTime ?? Math.round(duration)
        const elapsedSecs = duration / 1000
          currentMetrics.tokensPerSec = currentMetrics.tokensPerSec ?? (elapsedSecs > 0 ? Math.round(tokenCount / elapsedSecs) : 0)
        setLastMetrics({ ...currentMetrics })

        if (shouldAutoTitle) {
          await updateMutation.mutateAsync({
            id: activeId,
            title: createConversationTitle(userText),
          })
        }

        await queryClient.invalidateQueries({ queryKey: ['conversation', activeId] })
        await queryClient.invalidateQueries({ queryKey: ['conversations'] })

        if (activeId && accumulatedText.trim()) {
          try {
            const response = await api.get(`/api/v1/conversations/${activeId}`)
            const refreshedConversation = response.data as Conversation
            const latestAssistantMessage = [...refreshedConversation.messages]
              .reverse()
              .find((message) => message.role === 'assistant' && message.content.trim() === accumulatedText.trim())

            if (latestAssistantMessage) {
              setMessageMetrics((current) => ({
                ...current,
                [getMessageMetricKey(activeId, latestAssistantMessage.id)]: { ...currentMetrics },
              }))
            }
          } catch (metricError) {
            console.error('Error al asociar métricas al mensaje generado:', metricError)
          }
        }
      } catch (err: any) {
        console.error('Error durante la generación:', err)
      } finally {
        setIsStreaming(false)
        chatControllerRef.current = null
        setPendingUserMessage(null)
        pendingStreamingBufferRef.current = ''
        if (streamingFlushRef.current !== null) {
          cancelAnimationFrame(streamingFlushRef.current)
          streamingFlushRef.current = null
        }
        resetStreamingContent('')
      }
    },
    [
      isStreaming,
      activeId,
      activeConversation,
      conversations,
      inputText,
      attachments,
      updateMutation,
      selectedProvider,
      selectedProviderLabel,
      selectedModelValue,
      temperature,
      contextLength,
      enableContextHistory,
      setLastMetrics,
      resetStreamingContent,
      queryClient,
    ]
  )

  const handleRetry = useCallback(async () => {
    if (!activeConversation || activeConversation.messages.length < 2 || isStreaming) return

    const messages = activeConversation.messages
    const lastMsg = messages[messages.length - 1]
    const userMsg = messages[messages.length - 2]

    if (lastMsg.role !== 'assistant' || userMsg.role !== 'user') return

    try {
      await deleteMessageMutation.mutateAsync({
        conversationId: activeConversation.id,
        messageId: lastMsg.id,
      })
      await handleSendMessage(null, userMsg.content)
    } catch (err) {
      console.error('Error al reintentar generación:', err)
    }
  }, [activeConversation, deleteMessageMutation, handleSendMessage, isStreaming])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSendMessage(e)
      }
    },
    [handleSendMessage]
  )

  return (
    <section className={`grid ${showConversations ? 'grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]' : 'grid-cols-1'}`} style={{height: 'calc(100vh - 3.5rem)'}}>
      {/* Sidebar / Conversations Panel */}
      {showConversations && (
        <>
          {/* Mobile overlay - tap to close */}
          <div
            className="fixed inset-0 z-10 bg-black/50 backdrop-blur-sm lg:hidden"
            onClick={() => setShowConversations(false)}
            aria-hidden="true"
          />
          <aside className="fixed left-0 top-14 bottom-0 z-20 w-[260px] flex flex-col lg:relative lg:top-auto lg:bottom-auto lg:z-auto lg:w-auto lg:h-full">
            {/* Conversations History Card */}
            <Card className="flex min-w-0 flex-col h-full overflow-hidden p-0 rounded-none lg:rounded-2xl border-none lg:border-slate-800 lg:bg-slate-950/60">
              <div className="flex items-center justify-between gap-2 shrink-0 px-4 pt-4 pb-0">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500 font-semibold">Chats</p>
                  <h2 className="text-base font-bold text-white">Conversaciones</h2>
                </div>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setShowConversations(false)}
                    aria-label="Ocultar conversaciones"
                    title="Ocultar"
                    className="flex h-8 w-8 items-center justify-center rounded-xl border border-slate-700 text-slate-400 transition hover:border-slate-600 hover:text-slate-200"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                  <button
                    onClick={handleCreate}
                    disabled={createMutation.isPending}
                    aria-label="Crear nueva conversación"
                    title="Nueva conversación"
                    className="flex h-8 w-8 items-center justify-center rounded-xl bg-cyan-500 text-slate-950 transition hover:bg-cyan-400 disabled:opacity-50"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="h-4 w-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                    </svg>
                  </button>
                </div>
              </div>

              {/* Search bar */}
              <div className="relative mt-4 px-4 pb-4">
                <input
                  type="text"
                  placeholder="Buscar chat..."
                  aria-label="Buscar conversaciones"
                  value={searchVal}
                  onChange={(e) => setSearchVal(e.target.value)}
                  className="w-full rounded-2xl border border-slate-700 bg-slate-950 pl-10 pr-8 py-2.5 text-sm text-slate-100 outline-none focus:border-cyan-400 transition"
                />
                <div className="absolute inset-y-0 left-3 flex items-center pointer-events-none text-slate-500">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                {searchVal && (
                  <button
                    onClick={() => setSearchVal('')}
                    className="absolute inset-y-0 right-3 flex items-center text-slate-500 hover:text-slate-300"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>

            {/* History List */}
            <div className="mt-4 flex-1 overflow-y-auto space-y-1.5 px-4 min-h-0 pb-4">
              {isLoadingList ? (
                <div className="py-4 text-center text-sm text-slate-500" aria-live="polite">
                  <div className="mb-2">Cargando historial...</div>
                  <Skeleton count={4} />
                </div>
              ) : conversations.length === 0 ? (
                <div className="py-8 text-center text-sm text-slate-500">
                  {searchDebounced ? 'No se encontraron resultados.' : 'Sin conversaciones creadas.'}
                </div>
              ) : (
                conversations.map((chat) => {
                  const isActive = chat.id === activeId
                  const isEditing = chat.id === editingId

                  return (
                    <div
                      key={chat.id}
                      className={`group flex items-center justify-between rounded-2xl border px-3 py-2.5 transition ${
                        isActive
                          ? 'border-cyan-500 bg-cyan-950/20 text-white'
                          : 'border-slate-800 bg-slate-950/40 text-slate-300 hover:border-slate-700 hover:bg-slate-900/40'
                      }`}
                    >
                        {isEditing ? (
                        <input
                          type="text"
                          value={editTitle}
                          onChange={(e) => setEditTitle(e.target.value)}
                          onBlur={() => handleRename(chat.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleRename(chat.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          autoFocus
                          className="flex-1 bg-slate-950 px-2 py-1 text-sm text-white rounded-xl outline-none border border-cyan-500"
                        />
                      ) : (
                        <button
                          onClick={() => {
                            setActiveId(chat.id)
                            setEditingId(null)
                            // Close panel on mobile after selecting
                            if (window.matchMedia('(max-width: 1023px)').matches) {
                              setShowConversations(false)
                            }
                          }}
                          className="flex-1 text-left truncate text-sm font-medium py-0.5"
                        >
                          {chat.pinned && (
                            <span className="inline-block mr-1.5 text-cyan-400" title="Fijado">
                              📌
                            </span>
                          )}
                          {sanitizeTitleForDisplay(chat.title)}
                        </button>
                      )}

                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity ml-2">
                        {!isEditing && (
                          <>
                            <button
                              onClick={() => handleTogglePin(chat.id, chat.pinned)}
                              className={`p-1 rounded-lg hover:bg-slate-800 transition ${
                                chat.pinned ? 'text-cyan-400' : 'text-slate-500 hover:text-slate-300'
                              }`}
                              title={chat.pinned ? 'Desfijar' : 'Fijar'}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 8.25l-7.5 7.5-3.75-3.75" />
                              </svg>
                            </button>
                            <button
                              onClick={() => {
                                setEditingId(chat.id)
                                setEditTitle(chat.title)
                              }}
                              className="p-1 rounded-lg text-slate-500 hover:bg-slate-800 hover:text-slate-300 transition"
                              title="Renombrar"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                            <button
                              onClick={() => handleDelete(chat.id)}
                              className="p-1 rounded-lg text-slate-500 hover:bg-slate-800 hover:text-rose-400 transition"
                              title="Eliminar"
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>
          </Card>
        </aside>
        </>
      )}

      {/* Main Chat Panel */}
      <article className="flex min-w-0 flex-col overflow-hidden gap-0" style={{height: 'calc(100vh - 3.5rem)'}}>
        {/* Header */}
        <div className="border-b border-slate-800 bg-slate-950/90 px-4 py-3 shrink-0">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {!showConversations && (
                <button
                  type="button"
                  onClick={() => setShowConversations(true)}
                  aria-label="Mostrar conversaciones"
                  title="Mostrar conversaciones"
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-slate-700 text-slate-400 transition hover:border-slate-600 hover:text-slate-100"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-4 w-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                  </svg>
                </button>
              )}
              <div className="min-w-0">
                <div className="text-xs text-slate-500 uppercase tracking-wider">VISOR</div>
                <h1 className="text-base font-semibold text-white truncate">
                  {activeConversation ? sanitizeTitleForDisplay(activeConversation.title) : 'Chat rápido'}
                </h1>
              </div>
            </div>
            {devMode && (
              <span className="shrink-0 rounded-2xl border border-cyan-500/30 bg-cyan-950/30 px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-cyan-300">
                Modo Dev activo
              </span>
            )}
          </div>
        </div>

        <Card className="flex-1 min-h-0 p-0 overflow-hidden flex flex-col bg-slate-950/60 border-slate-800 rounded-none lg:rounded-none">
          {activeConversation ? (
            <div className="flex flex-col flex-1 h-full">
              {/* Message History */}
              <div className="flex-1 overflow-y-auto p-4 sm:p-6 pb-0 space-y-4">
                {isLoadingConversation ? (
                  <div className="flex items-center justify-center h-full text-slate-500 text-sm" aria-live="polite">
                    <div className="mb-3">Cargando mensajes...</div>
                    <Skeleton count={6} />
                  </div>
                ) : activeConversation.messages.length === 0 ? (
                  <div className="rounded-3xl border border-slate-800/50 bg-slate-950/50 p-6 sm:p-8 text-slate-400 shadow-inner shadow-slate-950/20 text-center">
                    <p className="font-medium text-slate-300">¡Nueva conversación iniciada!</p>
                    <p className="text-xs text-slate-500 mt-2">
                      Envía un mensaje para comenzar. Los mensajes se guardarán en tu historial de forma permanente.
                    </p>
                  </div>
                ) : (
                  activeConversation.messages.map((message, index) => {
                    const isUser = message.role === 'user'
                    const isLastMessage = index === activeConversation.messages.length - 1
                    const currentMessageMetrics = !isUser
                      ? messageMetrics[getMessageMetricKey(activeConversation.id, message.id)]
                      : null

                    return (
                      <div key={message.id} className="space-y-1">
                        <MessageBubble
                          role={isUser ? 'user' : 'assistant'}
                          content={message.content}
                        />

                        {/* Retry Button under the last assistant message */}
                        {!isUser && isLastMessage && !isStreaming && (
                          <div className="flex flex-col gap-2 pl-2">
                            <div className="flex items-center gap-3">
                              <button
                                onClick={handleRetry}
                                className="flex items-center gap-1 text-[10px] text-slate-500 hover:text-cyan-400 font-bold transition py-1"
                                title="Reintentar generación"
                              >
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3 h-3">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
                                </svg>
                                Reintentar
                              </button>
                              {(currentMessageMetrics ?? lastMetrics) && (currentMessageMetrics ?? lastMetrics)!.generationTime !== null && (
                                <span className="rounded-full border border-slate-700 bg-slate-950/90 px-2 py-1 text-[10px] text-slate-500">
                                  {formatDuration((currentMessageMetrics ?? lastMetrics)!.generationTime!)} · {(currentMessageMetrics ?? lastMetrics)!.tokensPerSec ?? 0} t/s
                                </span>
                              )}
                            </div>
                          </div>
                        )}

                        {!isUser && !isLastMessage && currentMessageMetrics && currentMessageMetrics.generationTime !== null && (
                          <div className="flex flex-col gap-2 pl-2">
                            <div className="flex items-center gap-3">
                              <span className="rounded-full border border-slate-700 bg-slate-950/90 px-2 py-1 text-[10px] text-slate-500">
                                {formatDuration(currentMessageMetrics.generationTime)} · {currentMessageMetrics.tokensPerSec ?? 0} t/s
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    )
                  })
                )}

                {pendingUserMessage && (
                  <div className="space-y-1">
                    <MessageBubble role="user" content={pendingUserMessage} />
                  </div>
                )}

                {/* Streaming Content (rendered virtually during generation) */}
                {isStreaming && streamingContent && (
                  <MessageBubble role="assistant" content={streamingContent} isStreaming />
                )}
                <div ref={messagesEndRef} />
              </div>

              {/* Developer Metrics Panel (collapsible debug display) */}
              {devMode && lastMetrics && (
                <div className="mx-6 mb-4 rounded-2xl border border-cyan-500/20 bg-slate-950/80 p-4 shadow-[0_0_20px_rgba(6,182,212,0.1)] backdrop-blur-sm">
                  <div className="flex items-center justify-between border-b border-slate-900 pb-2">
                    <span className="text-[10px] uppercase tracking-widest text-cyan-400 font-bold">🛠️ Métricas de Rendimiento</span>
                    <span className="text-[9px] font-mono text-slate-500">Proveedor: {lastMetrics.providerName} ({lastMetrics.modelName})</span>
                  </div>
                  <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs font-mono">
                    <div className="space-y-1">
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider">TTFT (Primer Token)</span>
                      <span className="text-white font-bold text-sm">
                        {lastMetrics.ttft !== null ? `${lastMetrics.ttft} ms` : 'esperando...'}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider">Velocidad</span>
                      <span className="text-emerald-400 font-bold text-sm">
                        {lastMetrics.tokensPerSec !== null ? `${lastMetrics.tokensPerSec} t/s` : '0 t/s'}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider">Tiempo de Gen</span>
                      <span className="text-white font-bold text-sm">
                        {lastMetrics.generationTime !== null ? `${(lastMetrics.generationTime / 1000).toFixed(2)} s` : 'en curso...'}
                      </span>
                    </div>
                    <div className="space-y-1">
                      <span className="text-slate-500 block text-[9px] uppercase tracking-wider">Tokens (In / Out)</span>
                      <span className="text-white font-bold text-sm">
                        {lastMetrics.inputTokens} / {lastMetrics.outputTokens}
                      </span>
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-4 border-t border-slate-900 pt-3 text-[11px] font-mono text-slate-400 sm:grid-cols-3">
                    <span>DB read: {lastMetrics.dbQueryMs ?? 0} ms</span>
                    <span>DB write: {lastMetrics.dbWriteMs ?? 0} ms</span>
                    <span>Contexto: {lastMetrics.contextBuildMs ?? 0} ms</span>
                    <span>Tokens: {lastMetrics.tokenCountMs ?? 0} ms</span>
                    <span>Prefill: {lastMetrics.prefillMs ?? 0} ms</span>
                    <span>Model call: {lastMetrics.modelCallMs ?? 0} ms</span>
                    <span>Msgs: {lastMetrics.selectedMessageCount ?? 0} / {lastMetrics.totalMessageCount ?? 0}</span>
                    <span>Hist tokens: {lastMetrics.totalHistoryTokens ?? 0}</span>
                    <span>Budget/reserva: {lastMetrics.contextBudgetTokens ?? 0} / {lastMetrics.responseTokenReserve ?? 0}</span>
                    <span>Resumen: {lastMetrics.summaryUsed ? `si (${lastMetrics.summaryGenerationMs ?? 0} ms)` : 'no'}</span>
                    <span>Cache: {lastMetrics.cacheHit ? 'hit' : 'miss'}</span>
                  </div>
                </div>
              )}

              {/* Chat Form */}
              <form onSubmit={(e) => handleSendMessage(e)} className="border-t border-slate-800 bg-slate-950/90 p-4 sm:p-6">
                <div className="rounded-3xl border border-slate-700 bg-slate-900/90 px-4 py-3 shadow-lg shadow-slate-950/30 transition focus-within:border-cyan-400">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    className="hidden"
                    accept="image/*,.txt,.md,.csv,.json,.xml,.log,.js,.ts,.tsx,.jsx,.py,.html,.css,.yaml,.yml,.pdf,.doc,.docx"
                    onChange={(event) => handleAttachFiles(event.target.files)}
                  />
                  {attachments.length > 0 && (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {attachments.map((attachment) => (
                        <span
                          key={attachment.id}
                          className="inline-flex max-w-full items-center gap-2 rounded-xl border border-slate-700 bg-slate-950/70 px-2.5 py-1.5 text-xs text-slate-300"
                          title={`${attachment.name} · ${formatFileSize(attachment.size)}`}
                        >
                          <span className="truncate max-w-[180px]">{attachment.name}</span>
                          <button
                            type="button"
                            onClick={() => setAttachments((current) => current.filter((item) => item.id !== attachment.id))}
                            className="text-slate-500 transition hover:text-rose-300"
                            aria-label={`Quitar ${attachment.name}`}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="flex items-end gap-3">
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      disabled={isStreaming}
                      aria-label="Adjuntar archivos"
                      title="Adjuntar archivos"
                      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-800 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.1} stroke="currentColor" className="h-5 w-5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l9.9-9.9a3 3 0 114.243 4.243l-9.193 9.193a1.5 1.5 0 01-2.121-2.121l8.486-8.486" />
                      </svg>
                    </button>
                    <textarea
                      ref={inputRef}
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyDown={handleKeyDown}
                      disabled={isStreaming}
                      rows={1}
                      aria-label="Escribe tu mensaje"
                      className="max-h-[180px] min-h-[38px] flex-1 resize-none bg-transparent text-sm leading-6 text-slate-100 outline-none placeholder:text-slate-500"
                      placeholder={isStreaming ? "Generando respuesta..." : "Escribe tu mensaje..."}
                    />
                    <button
                      type={isStreaming ? 'button' : 'submit'}
                      onClick={isStreaming ? handleStop : undefined}
                      disabled={!isStreaming && !inputText.trim() && attachments.length === 0}
                      aria-label={isStreaming ? 'Detener generación' : 'Enviar mensaje'}
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition disabled:cursor-not-allowed ${
                        isStreaming
                          ? 'bg-rose-500 text-white hover:bg-rose-400'
                          : 'bg-cyan-500 text-slate-950 hover:bg-cyan-400 disabled:bg-slate-700 disabled:text-slate-500'
                      }`}
                    >
                      {isStreaming ? (
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
                          <path d="M7 7h10v10H7z" />
                        </svg>
                      ) : (
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-5 h-5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
              </form>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center flex-1 p-8 text-center text-slate-500 min-h-[400px]">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor" className="w-16 h-16 text-slate-700 mb-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
              </svg>
              <h3 className="text-lg font-bold text-white mb-2">Comienza una conversación</h3>
              <p className="max-w-md text-sm mb-6">
                Selecciona una conversación del menú lateral o crea una nueva para empezar a chatear. Su historial se guardará localmente.
              </p>
              <button
                onClick={handleCreate}
                className="rounded-2xl bg-cyan-500 px-5 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 shadow-lg"
              >
                Crear conversación
              </button>
            </div>
          )}
        </Card>
      </article>

      {/* Delete Confirmation Modal */}
      {deleteConfirmId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="relative w-full max-w-sm rounded-3xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
            {/* Close Button */}
            <button
              onClick={() => setDeleteConfirmId(null)}
              className="absolute right-4 top-4 text-slate-400 hover:text-slate-200 transition"
              aria-label="Cerrar"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Content */}
            <div className="mb-6 text-center">
              <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-rose-500/20">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="h-6 w-6 text-rose-400">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c.866.276 1.753.519 2.654.72m15.298-1.279a47.863 47.863 0 00-2.603-.148dp3c-1.306 0-2.591.134-3.859.388m0 0a48.159 48.159 0 00-7.228-1.00c-3.798 0-7.35.75-10.584 2.118m7.422 6.609c1.395.37 2.821.645 4.266.822m7.422-6.609a48.159 48.159 0 00-7.228-1.00c-3.798 0-7.35.75-10.584 2.118m15.298 1.279c.866-.276 1.753-.519 2.654-.72M4.883 12.935c.378-.01.755-.009 1.131.014m15.298-1.279c1.306 0 2.59-.134 3.859-.388" />
                </svg>
              </div>
              <h3 className="text-lg font-bold text-white mb-2">¿Eliminar conversación?</h3>
              <p className="text-sm text-slate-400">
                Esta acción no se puede deshacer. La conversación y todo su historial se eliminarán permanentemente.
              </p>
            </div>

            {/* Buttons */}
            <div className="flex gap-3">
              <button
                onClick={() => setDeleteConfirmId(null)}
                disabled={deletingId !== null}
                className="flex-1 rounded-2xl border border-slate-700 px-4 py-2.5 text-sm font-semibold text-slate-300 transition hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Cancelar
              </button>
              <button
                onClick={confirmDelete}
                disabled={deletingId !== null}
                className="flex-1 rounded-2xl bg-rose-500 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-rose-400 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {deletingId !== null ? (
                  <>
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4 animate-spin">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12a3 3 0 100-6 3 3 0 000 6z" />
                    </svg>
                    Eliminando...
                  </>
                ) : (
                  'Sí, eliminar'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  )
}
