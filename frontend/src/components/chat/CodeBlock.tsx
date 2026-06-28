import { ReactNode, useMemo } from 'react'
import { CopyButton } from './CopyButton'

interface CodeBlockProps {
  children?: ReactNode
}

function extractText(node: ReactNode): string {
  if (typeof node === 'string') return node
  if (typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(extractText).join('')
  if (node && typeof node === 'object' && 'props' in node) {
    const element = node as { props: { children?: ReactNode } }
    return extractText(element.props.children)
  }
  return ''
}

function extractLanguage(node: ReactNode): string | null {
  if (Array.isArray(node)) {
    for (const child of node) {
      const lang = extractLanguage(child)
      if (lang) return lang
    }
    return null
  }

  if (node && typeof node === 'object' && 'props' in node) {
    const element = node as { props: { className?: string; children?: ReactNode } }
    const match = /language-([\w-]+)/.exec(element.props.className ?? '')
    if (match) return match[1]
    return extractLanguage(element.props.children)
  }

  return null
}

export function CodeBlock({ children }: CodeBlockProps) {
  const codeText = useMemo(() => extractText(children).replace(/\n$/, ''), [children])
  const language = useMemo(() => extractLanguage(children), [children])

  return (
    <div className="code-block group/code my-3 overflow-hidden rounded-xl border border-slate-700/80 bg-slate-950">
      <div className="flex items-center justify-between border-b border-slate-800 bg-slate-900/60 px-3 py-1.5">
        <span className="text-[10px] font-mono uppercase tracking-wider text-slate-500">
          {language ?? 'código'}
        </span>
        <CopyButton
          getText={() => codeText}
          label="Copiar"
          copiedLabel="Copiado"
          className="opacity-70 transition group-hover/code:opacity-100"
        />
      </div>
      <pre className="overflow-x-auto p-4 text-[13px] leading-relaxed">{children}</pre>
    </div>
  )
}
