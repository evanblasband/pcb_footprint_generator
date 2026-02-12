import { useState } from 'react'

/**
 * Control panel for extraction workflow.
 * Shows status, triggers extraction/confirm/download actions.
 */
function ControlPanel({
  jobStatus,
  extractionResult,
  error,
  pin1Required,
  selectedPin1,
  partNumber,
  imageCount = 1,
  onPartNumberChange,
  onExtract,
  onConfirm,
  onDownload,
  onReset,
}) {
  const [selectedModel, setSelectedModel] = useState('sonnet')

  const isLoading = ['uploading', 'extracting', 'confirming', 'generating'].includes(jobStatus)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">
          Extraction
        </h2>
        <button
          onClick={onReset}
          className="text-sm text-text-secondary hover:text-accent transition-colors"
        >
          Start Over
        </button>
      </div>

      {/* Error display */}
      {error && (
        <div className="bg-error/10 border border-error/30 rounded-lg p-3">
          <p className="text-sm text-error">{error}</p>
        </div>
      )}

      {/* Status indicator */}
      <div className="bg-bg-tertiary rounded-lg p-4 space-y-3">
        <StatusStep
          label={imageCount > 1 ? `Upload (${imageCount} images)` : "Upload"}
          status={getStepStatus('upload', jobStatus)}
        />
        <StatusStep
          label="Extract Dimensions"
          status={getStepStatus('extract', jobStatus)}
        />
        <StatusStep
          label="Confirm"
          status={getStepStatus('confirm', jobStatus)}
          note={pin1Required && jobStatus === 'extracted' ? 'Select Pin 1 on preview' : null}
        />
        <StatusStep
          label="Download"
          status={getStepStatus('download', jobStatus)}
        />
      </div>

      {/* Part number input */}
      <div className="space-y-2">
        <label className="block text-sm text-text-secondary">
          Part Number <span className="text-text-muted">(for filename)</span>
        </label>
        <input
          type="text"
          value={partNumber}
          onChange={(e) => onPartNumberChange(e.target.value)}
          placeholder="e.g., LM358, STM32F103"
          className="w-full bg-bg-tertiary border border-text-secondary/30 rounded-lg px-3 py-2
            text-text-primary placeholder:text-text-muted
            focus:outline-none focus:border-accent/50 transition-colors"
        />
      </div>

      {/* Action buttons */}
      <div className="space-y-3">
        {/* Extract button */}
        {jobStatus === 'uploaded' && (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <label className="text-sm text-text-secondary">Model:</label>
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="bg-bg-tertiary border border-text-secondary/30 rounded px-2 py-1 text-sm text-text-primary"
              >
                <option value="sonnet">Sonnet (Recommended)</option>
                <option value="haiku">Haiku (Faster)</option>
                <option value="opus">Opus (Complex TH)</option>
              </select>
            </div>
            <button
              onClick={() => onExtract(selectedModel)}
              disabled={isLoading}
              className="w-full bg-accent text-text-dark font-semibold py-3 px-4 rounded-lg
                hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Extract Dimensions
            </button>
          </div>
        )}

        {/* Confirm button */}
        {jobStatus === 'extracted' && (
          <button
            onClick={onConfirm}
            disabled={isLoading || (pin1Required && selectedPin1 === null)}
            className="w-full bg-accent text-text-dark font-semibold py-3 px-4 rounded-lg
              hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {pin1Required && selectedPin1 === null
              ? 'Select Pin 1 to Continue'
              : 'Confirm Dimensions'}
          </button>
        )}

        {/* Download button */}
        {(jobStatus === 'confirmed' || jobStatus === 'downloaded') && (
          <div className="space-y-1">
            <button
              onClick={onDownload}
              disabled={isLoading}
              className="w-full bg-accent text-text-dark font-semibold py-3 px-4 rounded-lg
                hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Download Script Package
            </button>
            {partNumber.trim() && (
              <p className="text-xs text-text-secondary text-center">
                {partNumber.trim().replace(/[^a-zA-Z0-9-_]/g, '_')}_ScriptProject.zip
              </p>
            )}
          </div>
        )}

        {/* Loading indicator */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 py-2">
            <div className="w-5 h-5 border-2 border-accent border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-text-secondary">
              {jobStatus === 'uploading' && 'Uploading...'}
              {jobStatus === 'extracting' && 'Extracting dimensions...'}
              {jobStatus === 'confirming' && 'Confirming...'}
              {jobStatus === 'generating' && 'Generating file...'}
            </span>
          </div>
        )}
      </div>

      {/* Extraction stats */}
      {extractionResult && (
        <div className="bg-bg-tertiary rounded-lg p-4 space-y-2">
          <h3 className="text-sm font-semibold text-text-primary">Results</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-text-secondary">Package:</span>
              <span className="ml-2 text-text-primary">
                {extractionResult.package_type || 'Custom'}
              </span>
            </div>
            <div>
              <span className="text-text-secondary">Confidence:</span>
              <span className={`ml-2 ${getConfidenceColor(extractionResult.overall_confidence)}`}>
                {Math.round((extractionResult.overall_confidence || 0) * 100)}%
              </span>
            </div>
          </div>
          {extractionResult.warnings?.length > 0 && (
            <div className="mt-2 pt-2 border-t border-text-secondary/20">
              <p className="text-xs text-warning">
                {extractionResult.warnings.length} warning(s)
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * Individual step in the status indicator.
 */
function StatusStep({ label, status, note }) {
  return (
    <div className="flex items-center gap-3">
      <div className={`
        w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold
        ${status === 'complete' ? 'bg-success text-text-dark' : ''}
        ${status === 'active' ? 'bg-accent text-text-dark' : ''}
        ${status === 'pending' ? 'bg-bg-secondary text-text-secondary' : ''}
      `}>
        {status === 'complete' ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : status === 'active' ? (
          <div className="w-2 h-2 bg-text-dark rounded-full animate-pulse" />
        ) : (
          <div className="w-2 h-2 bg-text-secondary rounded-full" />
        )}
      </div>
      <div className="flex-1">
        <span className={`text-sm ${status === 'pending' ? 'text-text-secondary' : 'text-text-primary'}`}>
          {label}
        </span>
        {note && (
          <p className="text-xs text-warning">{note}</p>
        )}
      </div>
    </div>
  )
}

/**
 * Get step status based on overall job status.
 */
function getStepStatus(step, jobStatus) {
  const statusMap = {
    upload: {
      idle: 'pending',
      uploading: 'active',
      uploaded: 'complete',
      extracting: 'complete',
      extracted: 'complete',
      confirming: 'complete',
      confirmed: 'complete',
      generating: 'complete',
      downloaded: 'complete',
    },
    extract: {
      idle: 'pending',
      uploading: 'pending',
      uploaded: 'pending',
      extracting: 'active',
      extracted: 'complete',
      confirming: 'complete',
      confirmed: 'complete',
      generating: 'complete',
      downloaded: 'complete',
    },
    confirm: {
      idle: 'pending',
      uploading: 'pending',
      uploaded: 'pending',
      extracting: 'pending',
      extracted: 'pending',
      confirming: 'active',
      confirmed: 'complete',
      generating: 'complete',
      downloaded: 'complete',
    },
    download: {
      idle: 'pending',
      uploading: 'pending',
      uploaded: 'pending',
      extracting: 'pending',
      extracted: 'pending',
      confirming: 'pending',
      confirmed: 'pending',
      generating: 'active',
      downloaded: 'complete',
    },
  }
  return statusMap[step]?.[jobStatus] || 'pending'
}

/**
 * Get color class for confidence value.
 */
function getConfidenceColor(confidence) {
  if (confidence >= 0.7) return 'text-success'
  if (confidence >= 0.5) return 'text-warning'
  return 'text-error'
}

export default ControlPanel
