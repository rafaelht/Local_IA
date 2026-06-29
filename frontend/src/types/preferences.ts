export interface UserPreferences {
  theme: 'dark' | 'light'
  dev_mode: boolean
  default_provider: 'liteRT' | 'ollama'
  default_model: string | null
  ollama_api_url: string
  litert_api_url: string
  temperature: number
  context_length: number
}

export interface FavoriteModel {
  id: number
  provider_name: 'liteRT' | 'ollama'
  model_name: string
  temperature: number
  context_length: number
}

export interface UserPreferencesUpdate {
  theme?: 'dark' | 'light'
  dev_mode?: boolean
  default_provider?: 'liteRT' | 'ollama'
  default_model?: string | null
  ollama_api_url?: string
  litert_api_url?: string
  temperature?: number
  context_length?: number
}

export interface FavoriteModelCreate {
  provider_name: 'liteRT' | 'ollama'
  model_name: string
  temperature?: number
  context_length?: number
}
