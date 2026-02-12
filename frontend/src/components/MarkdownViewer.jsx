import { useState, useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import mermaid from 'mermaid'

// Initialize mermaid with dark theme
mermaid.initialize({
  startOnLoad: false,
  theme: 'dark',
  themeVariables: {
    // Node colors - lime accent with dark text (readable)
    primaryColor: '#e6fb53',
    primaryTextColor: '#0d0d0d',
    primaryBorderColor: '#e6fb53',
    // Secondary/tertiary nodes - darker bg with light text
    secondaryColor: '#374151',
    secondaryTextColor: '#e5e5e5',
    tertiaryColor: '#4b5563',
    tertiaryTextColor: '#e5e5e5',
    // General colors
    lineColor: '#a3a3a3',
    background: '#1a1a1a',
    mainBkg: '#374151',
    secondBkg: '#4b5563',
    textColor: '#e5e5e5',
    // Node text should be light on dark backgrounds
    nodeBorder: '#e6fb53',
    clusterBkg: '#262626',
    clusterBorder: '#e6fb53',
    // Sequence diagram colors
    actorTextColor: '#e5e5e5',
    actorBkg: '#374151',
    actorBorder: '#e6fb53',
    signalColor: '#e5e5e5',
    signalTextColor: '#e5e5e5',
    messageTextColor: '#e5e5e5',
    labelBoxBkgColor: '#374151',
    labelBoxBorderColor: '#e6fb53',
    labelTextColor: '#e5e5e5',
    loopTextColor: '#e5e5e5',
    sequenceNumberColor: '#e5e5e5',
    noteBkgColor: '#4b5563',
    noteTextColor: '#e5e5e5',
    noteBorderColor: '#e6fb53',
    activationBkgColor: '#374151',
    activationBorderColor: '#e6fb53',
  },
  flowchart: {
    htmlLabels: true,
    curve: 'basis',
  },
})

/**
 * Component to render Mermaid diagrams.
 * Uses unique IDs to prevent conflicts when multiple diagrams exist.
 */
function MermaidDiagram({ chart }) {
  const containerRef = useRef(null)
  const [svg, setSvg] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    const renderDiagram = async () => {
      if (!chart || !containerRef.current) return

      try {
        // Generate unique ID for this diagram
        const id = `mermaid-${Math.random().toString(36).substring(2, 11)}`
        const { svg } = await mermaid.render(id, chart)
        setSvg(svg)
        setError(null)
      } catch (err) {
        console.error('Mermaid render error:', err)
        setError(err.message)
      }
    }

    renderDiagram()
  }, [chart])

  if (error) {
    return (
      <div className="bg-bg-tertiary p-4 rounded-lg mb-4 border border-error">
        <p className="text-error text-sm mb-2">Failed to render diagram:</p>
        <pre className="text-xs text-text-secondary overflow-x-auto">{chart}</pre>
      </div>
    )
  }

  return (
    <div
      ref={containerRef}
      className="bg-bg-tertiary p-4 rounded-lg mb-4 overflow-x-auto flex justify-center"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  )
}

/**
 * Component to fetch and render markdown documentation.
 * Supports GitHub Flavored Markdown and Mermaid diagrams.
 */
function MarkdownViewer({ docName }) {
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    const fetchDoc = async () => {
      setLoading(true)
      setError(null)

      try {
        const response = await fetch(`/api/docs/${docName}`)
        if (!response.ok) {
          throw new Error('Failed to load documentation')
        }
        const data = await response.json()
        setContent(data.content)
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }

    fetchDoc()
  }, [docName])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <p className="text-error">{error}</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      <article className="prose prose-invert prose-lime max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Custom styling for markdown elements
            h1: ({ children }) => (
              <h1 className="text-3xl font-bold text-text-primary mb-6 pb-2 border-b border-bg-tertiary">
                {children}
              </h1>
            ),
            h2: ({ children }) => (
              <h2 className="text-2xl font-semibold text-text-primary mt-8 mb-4">
                {children}
              </h2>
            ),
            h3: ({ children }) => (
              <h3 className="text-xl font-semibold text-text-primary mt-6 mb-3">
                {children}
              </h3>
            ),
            h4: ({ children }) => (
              <h4 className="text-lg font-semibold text-text-primary mt-4 mb-2">
                {children}
              </h4>
            ),
            p: ({ children }) => (
              <p className="text-text-secondary mb-4 leading-relaxed">
                {children}
              </p>
            ),
            ul: ({ children }) => (
              <ul className="list-disc list-inside mb-4 space-y-1 text-text-secondary">
                {children}
              </ul>
            ),
            ol: ({ children }) => (
              <ol className="list-decimal list-inside mb-4 space-y-1 text-text-secondary">
                {children}
              </ol>
            ),
            li: ({ children }) => (
              <li className="text-text-secondary">
                {children}
              </li>
            ),
            a: ({ href, children }) => (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:text-accent-hover underline"
              >
                {children}
              </a>
            ),
            // Handle code blocks - check for mermaid language
            code: ({ inline, className, children }) => {
              const match = /language-(\w+)/.exec(className || '')
              const language = match ? match[1] : ''

              // Render mermaid diagrams
              if (!inline && language === 'mermaid') {
                return <MermaidDiagram chart={String(children).trim()} />
              }

              if (inline) {
                return (
                  <code className="bg-bg-tertiary text-accent px-1.5 py-0.5 rounded text-sm font-mono">
                    {children}
                  </code>
                )
              }
              return (
                <code className="block bg-bg-tertiary p-4 rounded-lg overflow-x-auto text-sm font-mono text-text-secondary">
                  {children}
                </code>
              )
            },
            pre: ({ children }) => {
              // Check if the child is a mermaid diagram (already rendered)
              if (children?.props?.className?.includes('language-mermaid')) {
                return <>{children}</>
              }
              return (
                <pre className="bg-bg-tertiary p-4 rounded-lg overflow-x-auto mb-4">
                  {children}
                </pre>
              )
            },
            blockquote: ({ children }) => (
              <blockquote className="border-l-4 border-accent pl-4 italic text-text-secondary mb-4">
                {children}
              </blockquote>
            ),
            table: ({ children }) => (
              <div className="overflow-x-auto mb-4">
                <table className="min-w-full border border-bg-tertiary">
                  {children}
                </table>
              </div>
            ),
            thead: ({ children }) => (
              <thead className="bg-bg-tertiary">
                {children}
              </thead>
            ),
            th: ({ children }) => (
              <th className="px-4 py-2 text-left text-text-primary font-semibold border border-bg-tertiary">
                {children}
              </th>
            ),
            td: ({ children }) => (
              <td className="px-4 py-2 text-text-secondary border border-bg-tertiary">
                {children}
              </td>
            ),
            hr: () => (
              <hr className="border-bg-tertiary my-8" />
            ),
            strong: ({ children }) => (
              <strong className="font-semibold text-text-primary">
                {children}
              </strong>
            ),
            em: ({ children }) => (
              <em className="italic text-text-secondary">
                {children}
              </em>
            ),
          }}
        >
          {content}
        </ReactMarkdown>
      </article>
    </div>
  )
}

export default MarkdownViewer
