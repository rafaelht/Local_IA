export interface Message {
  id: number
  conversation_id: number
  role: string
  content: string
  created_at: string
}

export interface Conversation {
  id: number
  title: string
  pinned: boolean
  favorite: boolean
  created_at: string
  updated_at: string
  messages: Message[]
}
