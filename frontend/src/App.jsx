import { useState, useCallback } from 'react'
import UploadPanel from './components/UploadPanel'
import ControlPanel from './components/ControlPanel'
import PreviewCanvas from './components/PreviewCanvas'
import DimensionTable from './components/DimensionTable'

/**
 * Main application component with two-panel layout.
 * Left panel: Upload, controls, dimension table
 * Right panel: 2D footprint preview canvas
 */
function App() {
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
  const handleExtract = useCallback(async (model = 'sonnet') => {
    if (!jobId) return

    setError(null)
    setJobStatus('extracting')

    try {
      const response = await fetch(`/api/extract/${jobId}?model=${model}`)

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

  return (
    <div className="min-h-screen bg-bg-primary">
      {/* Header */}
      <header className="border-b border-bg-tertiary px-6 py-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-text-primary">
            <span className="text-accent">Footprint</span>AI
          </h1>
          <span className="text-sm text-text-secondary">
            PCB Footprint Generator
          </span>
        </div>
      </header>

      {/* Main content - two panel layout */}
      <main className="flex h-[calc(100vh-73px)]">
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
    </div>
  )
}

export default App
