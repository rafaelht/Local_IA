import { memo, useCallback } from 'react'
import { MarkdownRenderer } from './MarkdownRenderer'
import { CopyButton } from './CopyButton'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  isStreaming?: boolean
}

function MessageBubbleInner({ role, content, isStreaming = false }: MessageBubbleProps) {
  const isUser = role === 'user'
  const getCopyText = useCallback(() => content, [content])

  return (
    <div className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        role="article"
        aria-label={isUser ? 'Mensaje del usuario' : isStreaming ? 'Asistente generando' : 'Mensaje del asistente'}
        aria-live={isUser ? undefined : 'polite'}
        className={`group relative max-w-[92%] rounded-2xl px-3 py-3 shadow-md sm:max-w-[80%] sm:px-4 ${
          isUser
            ? 'rounded-br-none bg-cyan-500 font-medium text-slate-950'
            : 'rounded-bl-none border border-slate-800 bg-slate-900 text-slate-200'
        }`}
        tabIndex={0}
      >
        <div className="mb-1 flex items-center justify-between gap-3">
          <p
            className={`text-[10px] font-bold uppercase tracking-wider ${
              isUser ? 'text-slate-800' : 'text-cyan-400'
            }`}
          >
            {isUser ? 'Tú' : isStreaming ? 'Asistente (Generando...)' : 'Asistente'}
          </p>
          {!isStreaming && content.trim().length > 0 && (
            <CopyButton
              getText={getCopyText}
              label="Copiar"
              copiedLabel="Copiado"
              className="shrink-0 opacity-0 transition group-hover:opacity-100 focus:opacity-100"
            />
          )}
        </div>

        {isUser ? (
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{content}</p>
        ) : (
          <MarkdownRenderer content={content} isStreaming={isStreaming} />
        )}
      </div>
    </div>
  )
}

export const MessageBubble = memo(
  MessageBubbleInner,
  (prev, next) =>
    prev.content === next.content &&
    prev.role === next.role &&
    prev.isStreaming === next.isStreaming
)
