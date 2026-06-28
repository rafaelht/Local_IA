export type ProviderName = 'liteRT' | 'ollama'

export interface ModelInfo {
  id: string
  name: string
  description?: string
}

export interface ChatAttachment {
  name: string
  type: string
  size: number
  kind: 'image' | 'text' | 'binary'
  content?: string
  dataUrl?: string
}

export interface ProviderClient {
  name: ProviderName
  listModels(): Promise<ModelInfo[]>
  health(): Promise<boolean>
  generate(prompt: string, options?: Record<string, unknown>): Promise<string>
  stream(prompt: string, options: Record<string, unknown>, onData: (chunk: string) => void): Promise<void>
  cancel(): void
}
