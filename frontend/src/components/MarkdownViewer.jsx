import { useState, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Component to fetch and render markdown documentation.
 */
function MarkdownViewer({ docName, title }) {
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
            code: ({ inline, children }) => {
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
            pre: ({ children }) => (
              <pre className="bg-bg-tertiary p-4 rounded-lg overflow-x-auto mb-4">
                {children}
              </pre>
            ),
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
