import { useState, useCallback } from 'react'
import UploadPanel from './components/UploadPanel'
import ControlPanel from './components/ControlPanel'
import PreviewCanvas from './components/PreviewCanvas'
import DimensionTable from './components/DimensionTable'
import MarkdownViewer from './components/MarkdownViewer'

// Navigation tabs configuration
const TABS = [
  { id: 'app', label: 'Generator' },
  { id: 'readme', label: 'README' },
  { id: 'prd', label: 'PRD' },
  { id: 'technical', label: 'Technical Decisions' },
]

// GitHub repository URL
const GITHUB_URL = 'https://github.com/evanblasband/pcb_footprint_generator'

/**
 * Main application component with tabbed navigation.
 * - Generator tab: Upload, controls, dimension table, preview canvas
 * - Documentation tabs: README, PRD, Technical Decisions
 */
function App() {
  // Active tab state
  const [activeTab, setActiveTab] = useState('app')

  // Job state
  const [jobId, setJobId] = useState(null)
  const [jobStatus, setJobStatus] = useState('idle') // idle, uploading, uploaded, extracting, extracted, confirming, confirmed, generating

  // Extraction results
  const [extractionResult, setExtractionResult] = useState(null)
  const [footprint, setFootprint] = useState(null)

  // Pin 1 selection
  const [selectedPin1, setSelectedPin1] = useState(null)
  const [pin1Required, setPin1Required] = useState(false)

  // Part number for filename
  const [partNumber, setPartNumber] = useState('')

  // Image count
  const [imageCount, setImageCount] = useState(0)

  // Error state
  const [error, setError] = useState(null)

  /**
   * Handle file upload (supports single file or array of files)
   */
  const handleUpload = useCallback(async (files) => {
    setError(null)
    setJobStatus('uploading')

    // Ensure files is an array
    const fileArray = Array.isArray(files) ? files : [files]

    try {
      const formData = new FormData()
      fileArray.forEach(file => {
        formData.append('files', file)
      })

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await response.json()
      setJobId(data.job_id)
      setImageCount(data.image_count || fileArray.length)
      setJobStatus('uploaded')
    } catch (err) {
      setError(err.message)
      setJobStatus('idle')
    }
  }, [])

  /**
   * Trigger extraction
   */
  const handleExtract = useCallback(async (model = 'sonnet', staged = false, verify = false, examples = false) => {
    if (!jobId) return

    setError(null)
    setJobStatus('extracting')

    try {
      const response = await fetch(`/api/extract/${jobId}?model=${model}&staged=${staged}&verify=${verify}&examples=${examples}`)

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Extraction failed')
      }

      const data = await response.json()

      if (!data.success) {
        throw new Error(data.error || 'Extraction failed')
      }

      setExtractionResult(data.extraction_result)
      setFootprint(data.footprint)
      setJobStatus('extracted')

      // Check if Pin 1 selection is required
      if (!data.pin1_detected) {
        setPin1Required(true)
      } else {
        setSelectedPin1(data.pin1_index)
      }
    } catch (err) {
      setError(err.message)
      setJobStatus('uploaded')
    }
  }, [jobId])

  /**
   * Confirm extraction and Pin 1
   */
  const handleConfirm = useCallback(async () => {
    if (!jobId) return

    setError(null)
    setJobStatus('confirming')

    try {
      const response = await fetch(`/api/confirm/${jobId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin1_index: selectedPin1 }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Confirmation failed')
      }

      setJobStatus('confirmed')
    } catch (err) {
      setError(err.message)
      setJobStatus('extracted')
    }
  }, [jobId, selectedPin1])

  /**
   * Download generated file
   */
  const handleDownload = useCallback(async () => {
    if (!jobId) return

    setError(null)
    setJobStatus('generating')

    try {
      const response = await fetch(`/api/generate/${jobId}`)

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Generation failed')
      }

      // Use part number for filename, or fall back to server-provided name
      let filename = 'FootprintScript.zip'
      if (partNumber.trim()) {
        // Sanitize part number for use as filename
        const sanitized = partNumber.trim().replace(/[^a-zA-Z0-9-_]/g, '_')
        filename = `${sanitized}_ScriptProject.zip`
      } else {
        // Get filename from Content-Disposition header
        const disposition = response.headers.get('Content-Disposition')
        const filenameMatch = disposition?.match(/filename="?(.+?)"?$/)
        if (filenameMatch) {
          filename = filenameMatch[1]
        }
      }

      // Download the file
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setJobStatus('downloaded')
    } catch (err) {
      setError(err.message)
      setJobStatus('confirmed')
    }
  }, [jobId, partNumber])

  /**
   * Reset to start over
   */
  const handleReset = useCallback(() => {
    setJobId(null)
    setJobStatus('idle')
    setExtractionResult(null)
    setFootprint(null)
    setSelectedPin1(null)
    setPin1Required(false)
    setPartNumber('')
    setImageCount(0)
    setError(null)
  }, [])

  /**
   * Render the main generator page
   */
  const renderGeneratorPage = () => (
    <main className="flex h-[calc(100vh-57px)]">
      {/* Left Panel - Controls */}
      <div className="w-[400px] min-w-[400px] border-r border-bg-tertiary overflow-y-auto">
        <div className="p-6 space-y-6">
          {/* Upload or status section */}
          {jobStatus === 'idle' ? (
            <UploadPanel onUpload={handleUpload} />
          ) : (
            <ControlPanel
              jobStatus={jobStatus}
              extractionResult={extractionResult}
              error={error}
              pin1Required={pin1Required}
              selectedPin1={selectedPin1}
              partNumber={partNumber}
              imageCount={imageCount}
              onPartNumberChange={setPartNumber}
              onExtract={handleExtract}
              onConfirm={handleConfirm}
              onDownload={handleDownload}
              onReset={handleReset}
            />
          )}

          {/* Dimension table */}
          {footprint && (
            <DimensionTable
              footprint={footprint}
              extractionResult={extractionResult}
            />
          )}
        </div>
      </div>

      {/* Right Panel - Preview */}
      <div className="flex-1 bg-bg-secondary">
        <PreviewCanvas
          footprint={footprint}
          selectedPin1={selectedPin1}
          pin1Required={pin1Required}
          onSelectPin1={setSelectedPin1}
        />
      </div>
    </main>
  )

  /**
   * Render a documentation page
   */
  const renderDocPage = (docName) => (
    <main className="h-[calc(100vh-57px)] overflow-y-auto bg-bg-secondary">
      <MarkdownViewer docName={docName} />
    </main>
  )

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header with tabs */}
      <header className="border-b border-bg-tertiary">
        <div className="flex items-center justify-between px-6 py-3">
          {/* Logo and tabs */}
          <div className="flex items-center gap-8">
            {/* Logo */}
            <h1
              className="text-xl font-bold text-text-primary cursor-pointer"
              onClick={() => setActiveTab('app')}
            >
              <span className="text-accent">Footprint</span>AI
            </h1>

            {/* Navigation tabs */}
            <nav className="flex items-center gap-1">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`
                    px-4 py-2 text-sm font-medium rounded-lg transition-colors
                    ${activeTab === tab.id
                      ? 'bg-bg-tertiary text-accent'
                      : 'text-text-secondary hover:text-text-primary hover:bg-bg-tertiary/50'
                    }
                  `}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {/* GitHub link */}
          <a
            href={GITHUB_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-text-secondary hover:text-text-primary transition-colors"
          >
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
              <path fillRule="evenodd" clipRule="evenodd" d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.34-3.369-1.34-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z" />
            </svg>
            GitHub
          </a>
        </div>
      </header>

      {/* Page content based on active tab */}
      {activeTab === 'app' && renderGeneratorPage()}
      {activeTab === 'readme' && renderDocPage('readme')}
      {activeTab === 'prd' && renderDocPage('prd')}
      {activeTab === 'technical' && renderDocPage('technical-decisions')}
    </div>
  )
}

export default App
