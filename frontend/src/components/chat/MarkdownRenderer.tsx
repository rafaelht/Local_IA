import { memo, useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import rehypeHighlight from 'rehype-highlight'
import rehypeKatex from 'rehype-katex'
import type { Components } from 'react-markdown'
import { CodeBlock } from './CodeBlock'
import 'katex/dist/katex.min.css'

interface MarkdownRendererProps {
  content: string
  /** Durante streaming se omite syntax highlighting para reducir coste de render. */
  isStreaming?: boolean
}

const markdownComponents: Components = {
  pre: ({ children }) => <CodeBlock>{children}</CodeBlock>,
  code: ({ className, children, ...props }) => {
    const isBlock = Boolean(className?.startsWith('language-'))

    if (isBlock) {
      return (
        <code className={className} {...props}>
          {children}
        </code>
      )
    }

    return (
      <code className="markdown-inline-code" {...props}>
        {children}
      </code>
    )
  },
  a: ({ href, children, ...props }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="markdown-link"
      {...props}
    >
      {children}
    </a>
  ),
  table: ({ children, ...props }) => (
    <div className="markdown-table-wrapper">
      <table className="markdown-table" {...props}>
        {children}
      </table>
    </div>
  ),
}

function MarkdownRendererInner({ content, isStreaming = false }: MarkdownRendererProps) {
  const remarkPlugins = useMemo(() => [remarkGfm, remarkMath], [])
  const rehypePlugins = useMemo(
    () => (isStreaming ? [rehypeKatex] : [rehypeKatex, rehypeHighlight]),
    [isStreaming]
  )

  return (
    <div className={`markdown-body text-sm leading-relaxed ${isStreaming ? 'markdown-streaming' : ''}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={markdownComponents}
      >
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="streaming-cursor" aria-hidden="true" />}
    </div>
  )
}

export const MarkdownRenderer = memo(MarkdownRendererInner)
