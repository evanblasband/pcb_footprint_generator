import { useState, useCallback, useRef, useEffect } from 'react'

/**
 * Drag-and-drop upload panel for datasheet images.
 * Supports multiple images for better extraction context.
 * Supports drag-drop, file browse, and clipboard paste (Ctrl+V / Cmd+V).
 */
function UploadPanel({ onUpload }) {
  const [isDragging, setIsDragging] = useState(false)
  const [previews, setPreviews] = useState([]) // Array of {id, url, name, size, file}
  const fileInputRef = useRef(null)
  const containerRef = useRef(null)

  /**
   * Handle paste events for clipboard image upload.
   */
  const handlePaste = useCallback((e) => {
    const items = e.clipboardData?.items
    if (!items) return

    for (const item of items) {
      if (item.type.startsWith('image/')) {
        e.preventDefault()
        const file = item.getAsFile()
        if (file) {
          addFile(file)
        }
        return
      }
    }
  }, [])

  // Listen for paste events on the document
  useEffect(() => {
    document.addEventListener('paste', handlePaste)
    return () => document.removeEventListener('paste', handlePaste)
  }, [handlePaste])

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

    const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'))
    files.forEach(file => addFile(file))
  }, [])

  const handleFileInput = useCallback((e) => {
    const files = Array.from(e.target.files)
    files.forEach(file => addFile(file))
    // Reset input so the same file can be selected again
    e.target.value = ''
  }, [])

  /**
   * Add a file to the previews list.
   */
  const addFile = (file) => {
    // Generate a name for pasted images (they come without names)
    const fileName = file.name || `pasted-image-${Date.now()}.png`
    const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`

    // Show preview
    const reader = new FileReader()
    reader.onload = (e) => {
      setPreviews(prev => [...prev, {
        id,
        url: e.target.result,
        name: fileName,
        size: (file.size / 1024).toFixed(1) + ' KB',
        file,
      }])
    }
    reader.readAsDataURL(file)
  }

  /**
   * Remove an image from the list.
   */
  const removeImage = (id) => {
    setPreviews(prev => prev.filter(p => p.id !== id))
  }

  /**
   * Handle upload button click.
   */
  const handleUploadClick = () => {
    if (previews.length > 0) {
      const files = previews.map(p => p.file)
      onUpload(files)
    }
  }

  const handleClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-text-primary">
        Upload Datasheet Images
      </h2>

      <div
        ref={containerRef}
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-lg p-6 text-center cursor-pointer
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
          multiple
          className="hidden"
        />

        <div className="text-4xl mb-3">
          <svg
            className="w-10 h-10 mx-auto text-text-secondary"
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
        <p className="text-text-primary mb-1">
          Drop, paste, or click to add images
        </p>
        <p className="text-sm text-text-secondary">
          PNG, JPEG, GIF, or WebP up to 10MB each
        </p>
        <p className="text-xs text-text-muted mt-1">
          Ctrl+V / Cmd+V to paste from clipboard
        </p>
      </div>

      {/* Image previews */}
      {previews.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-text-secondary">
              {previews.length} image{previews.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                setPreviews([])
              }}
              className="text-xs text-text-muted hover:text-error transition-colors"
            >
              Clear all
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {previews.map((preview, index) => (
              <div
                key={preview.id}
                className="relative group bg-bg-tertiary rounded-lg p-2"
                onClick={(e) => e.stopPropagation()}
              >
                <img
                  src={preview.url}
                  alt={`Preview ${index + 1}`}
                  className="w-full h-24 object-cover rounded"
                />
                <div className="mt-1">
                  <p className="text-xs text-text-primary truncate" title={preview.name}>
                    {preview.name}
                  </p>
                  <p className="text-xs text-text-muted">{preview.size}</p>
                </div>
                {/* Remove button */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    removeImage(preview.id)
                  }}
                  className="absolute top-1 right-1 w-5 h-5 bg-bg-primary/80 hover:bg-error text-text-secondary hover:text-white rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all"
                  title="Remove image"
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          {/* Upload button */}
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleUploadClick()
            }}
            className="w-full py-2 px-4 bg-accent text-bg-primary font-semibold rounded-lg hover:bg-accent/90 transition-colors"
          >
            Upload {previews.length} Image{previews.length !== 1 ? 's' : ''}
          </button>
        </div>
      )}

      <div className="text-xs text-text-secondary space-y-1">
        <p>
          <strong>Tip:</strong> Upload multiple images (dimension drawing, pin diagram, tables)
          for better extraction accuracy.
        </p>
      </div>
    </div>
  )
}

export default UploadPanel
