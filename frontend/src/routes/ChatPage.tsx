import ChatLayout from '../components/layout/ChatLayout'
import { useProtectedRoute } from '../hooks/useProtectedRoute'

export default function ChatPage() {
  useProtectedRoute()
  return <ChatLayout />
}
