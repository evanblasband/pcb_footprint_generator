import { useState, useCallback, useRef } from 'react'

/**
 * Drag-and-drop upload panel for datasheet images.
 */
function UploadPanel({ onUpload }) {
  const [isDragging, setIsDragging] = useState(false)
  const [preview, setPreview] = useState(null)
  const fileInputRef = useRef(null)

  const handleDragOver = useCallback((e) => {
    e.preventDefault()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)
  }, [])

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) {
      handleFile(file)
    }
  }, [])

  const handleFileInput = useCallback((e) => {
    const file = e.target.files[0]
    if (file) {
      handleFile(file)
    }
  }, [])

  const handleFile = (file) => {
    // Show preview
    const reader = new FileReader()
    reader.onload = (e) => {
      setPreview({
        url: e.target.result,
        name: file.name,
        size: (file.size / 1024).toFixed(1) + ' KB',
      })
    }
    reader.readAsDataURL(file)

    // Trigger upload
    onUpload(file)
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text-primary">
        Upload Datasheet Image
      </h2>

      <div
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
          transition-all duration-200
          ${isDragging
            ? 'border-accent bg-accent/10'
            : 'border-text-secondary/30 hover:border-accent/50 hover:bg-bg-tertiary'
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          onChange={handleFileInput}
          className="hidden"
        />

        {preview ? (
          <div className="space-y-3">
            <img
              src={preview.url}
              alt="Preview"
              className="max-h-40 mx-auto rounded"
            />
            <p className="text-sm text-text-primary">{preview.name}</p>
            <p className="text-xs text-text-secondary">{preview.size}</p>
          </div>
        ) : (
          <>
            <div className="text-4xl mb-4">
              <svg
                className="w-12 h-12 mx-auto text-text-secondary"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                />
              </svg>
            </div>
            <p className="text-text-primary mb-2">
              Drop image here or click to browse
            </p>
            <p className="text-sm text-text-secondary">
              PNG, JPEG, GIF, or WebP up to 10MB
            </p>
          </>
        )}
      </div>

      <div className="text-xs text-text-secondary space-y-1">
        <p>
          <strong>Tip:</strong> Crop the image to show only the land pattern
          drawing for best results.
        </p>
      </div>
    </div>
  )
}

export default UploadPanel
