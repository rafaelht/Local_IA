import axios from 'axios'
import api from '../lib/api'
import type { ChatAttachment, ModelInfo, ProviderClient } from './provider'

function buildMessages(prompt: string, options?: Record<string, unknown>) {
  const attachments = (options?.attachments as ChatAttachment[] | undefined) ?? []
  const images = attachments.filter((attachment) => attachment.kind === 'image' && attachment.dataUrl)

  if (images.length === 0) {
    return [{ role: 'user', content: prompt }]
  }

  return [
    {
      role: 'user',
      content: [
        { type: 'text', text: prompt },
        ...images.map((attachment) => ({
          type: 'image_url',
          image_url: { url: attachment.dataUrl },
        })),
      ],
    },
  ]
}

export class OllamaProvider implements ProviderClient {
  name: 'ollama' = 'ollama'
  private baseUrl = '/ollama-api'
  private controller: AbortController | null = null

  cancel(): void {
    if (this.controller) {
      this.controller.abort()
      this.controller = null
    }
  }

  async health(): Promise<boolean> {
    try {
      const response = await api.get('/api/v1/preferences/providers/ollama/health')
      return response.data.healthy === true
    } catch {
      return false
    }
  }

  async listModels(): Promise<ModelInfo[]> {
    try {
      const response = await api.get('/api/v1/preferences/providers/ollama/models')
      const models = response.data.data || []
      return models.map((m: any) => ({
        id: m.id,
        name: m.id,
        description: 'Modelo local en Ollama'
      }))
    } catch (error) {
      console.error('Error al listar modelos de Ollama:', error)
      return []
    }
  }

  async generate(prompt: string, options?: Record<string, unknown>): Promise<string> {
    this.controller = new AbortController()
    try {
      const response = await axios.post(
        `${this.baseUrl}/v1/chat/completions`,
        {
          model: options?.model || 'default',
          messages: buildMessages(prompt, options),
          temperature: options?.temperature ?? 0.7,
          max_tokens: options?.max_tokens,
          stream: false
        },
        { signal: this.controller.signal }
      )
      return response.data.choices[0].message.content
    } catch (error) {
      if (axios.isCancel(error)) {
        throw new Error('Generación cancelada')
      }
      throw error
    } finally {
      this.controller = null
    }
  }

  async stream(prompt: string, options: Record<string, unknown>, onData: (chunk: string) => void): Promise<void> {
    this.controller = new AbortController()
    try {
      const response = await fetch(`${this.baseUrl}/v1/chat/completions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: options.model || 'default',
          messages: buildMessages(prompt, options),
          temperature: options.temperature ?? 0.7,
          max_tokens: options.max_tokens,
          stream: true
        }),
        signal: this.controller.signal
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

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const cleanLine = line.trim()
          if (!cleanLine) continue
          if (cleanLine === 'data: [DONE]') {
            break
          }
          if (cleanLine.startsWith('data: ')) {
            try {
              const dataStr = cleanLine.substring(6).trim()
              if (!dataStr) continue
              const parsed = JSON.parse(dataStr)
              const chunk = parsed.choices[0]?.delta?.content || ''
              if (chunk) {
                onData(chunk)
              }
            } catch (err) {
              console.error('Error al parsear fragmento SSE:', err, 'Línea:', cleanLine)
            }
          }
        }
      }
    } catch (error: any) {
      if (error.name === 'AbortError' || (error instanceof DOMException && error.name === 'AbortError')) {
        throw new Error('Generación cancelada')
      }
      throw error
    } finally {
      this.controller = null
    }
  }
}
