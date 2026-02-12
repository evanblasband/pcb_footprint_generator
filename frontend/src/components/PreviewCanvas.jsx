import { useRef, useEffect, useState, useCallback } from 'react'

/**
 * 2D canvas preview of the footprint.
 * Shows pads with labels, allows Pin 1 selection when required.
 */
function PreviewCanvas({ footprint, selectedPin1, pin1Required, onSelectPin1 }) {
  const canvasRef = useRef(null)
  const containerRef = useRef(null)
  const [scale, setScale] = useState(1)
  const [offset, setOffset] = useState({ x: 0, y: 0 })
  const [hoveredPad, setHoveredPad] = useState(null)

  // Coordinate conversion (mm to canvas pixels)
  const MM_TO_PX = 50 // 50 pixels per mm

  /**
   * Calculate canvas dimensions and scale to fit footprint.
   */
  const calculateTransform = useCallback(() => {
    if (!footprint?.pads?.length || !containerRef.current) return

    const container = containerRef.current
    const { width: containerWidth, height: containerHeight } = container.getBoundingClientRect()

    // Find bounding box of all pads
    let minX = Infinity, maxX = -Infinity
    let minY = Infinity, maxY = -Infinity

    footprint.pads.forEach(pad => {
      const halfW = (pad.width || 1) / 2
      const halfH = (pad.height || 1) / 2
      minX = Math.min(minX, pad.x - halfW)
      maxX = Math.max(maxX, pad.x + halfW)
      minY = Math.min(minY, pad.y - halfH)
      maxY = Math.max(maxY, pad.y + halfH)
    })

    // Add padding
    const padding = 2 // mm
    minX -= padding
    maxX += padding
    minY -= padding
    maxY += padding

    const fpWidth = maxX - minX
    const fpHeight = maxY - minY

    // Calculate scale to fit
    const scaleX = (containerWidth - 40) / (fpWidth * MM_TO_PX)
    const scaleY = (containerHeight - 40) / (fpHeight * MM_TO_PX)
    const newScale = Math.min(scaleX, scaleY, 2) // Cap at 2x

    // Center offset
    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2

    setScale(newScale)
    setOffset({
      x: containerWidth / 2 - centerX * MM_TO_PX * newScale,
      y: containerHeight / 2 + centerY * MM_TO_PX * newScale, // Flip Y
    })
  }, [footprint])

  // Recalculate on footprint change or resize
  useEffect(() => {
    calculateTransform()

    const handleResize = () => calculateTransform()
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [calculateTransform])

  /**
   * Draw the footprint on canvas.
   */
  useEffect(() => {
    const canvas = canvasRef.current
    const container = containerRef.current
    if (!canvas || !container) return

    const { width, height } = container.getBoundingClientRect()
    canvas.width = width
    canvas.height = height

    const ctx = canvas.getContext('2d')

    // Clear
    ctx.fillStyle = '#141311'
    ctx.fillRect(0, 0, width, height)

    // Draw grid
    drawGrid(ctx, width, height, scale, offset)

    if (!footprint?.pads?.length) {
      // Draw placeholder
      ctx.fillStyle = '#656462'
      ctx.font = '16px Inter, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText('Upload an image to preview footprint', width / 2, height / 2)
      return
    }

    // Calculate outline bounds for consistent positioning
    const outlineBounds = calculateOutlineBounds(footprint.pads, 0.3)

    // Draw outline
    drawOutline(ctx, footprint.outline, scale, offset, MM_TO_PX, footprint.pads)

    // Draw pads
    footprint.pads.forEach((pad, index) => {
      const isPin1 = selectedPin1 === index
      const isHovered = hoveredPad === index
      drawPad(ctx, pad, index, scale, offset, MM_TO_PX, isPin1, isHovered, pin1Required, outlineBounds)
    })

    // Draw spacing dimensions
    drawSpacingDimensions(ctx, footprint.pads, scale, offset, MM_TO_PX)

    // Draw origin crosshair
    drawOrigin(ctx, scale, offset)

  }, [footprint, scale, offset, selectedPin1, hoveredPad, pin1Required])

  /**
   * Handle mouse move for hover detection.
   */
  const handleMouseMove = useCallback((e) => {
    if (!footprint?.pads?.length || !canvasRef.current) return

    const rect = canvasRef.current.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    // Convert to mm coordinates
    const mmX = (mouseX - offset.x) / (MM_TO_PX * scale)
    const mmY = -(mouseY - offset.y) / (MM_TO_PX * scale) // Flip Y

    // Check if hovering over any pad
    let found = null
    footprint.pads.forEach((pad, index) => {
      const halfW = (pad.width || 1) / 2
      const halfH = (pad.height || 1) / 2
      if (
        mmX >= pad.x - halfW &&
        mmX <= pad.x + halfW &&
        mmY >= pad.y - halfH &&
        mmY <= pad.y + halfH
      ) {
        found = index
      }
    })

    setHoveredPad(found)
  }, [footprint, offset, scale])

  /**
   * Handle click for Pin 1 selection.
   */
  const handleClick = useCallback(() => {
    if (pin1Required && hoveredPad !== null) {
      onSelectPin1(hoveredPad)
    }
  }, [pin1Required, hoveredPad, onSelectPin1])

  return (
    <div
      ref={containerRef}
      className="w-full h-full relative"
      style={{ cursor: pin1Required && hoveredPad !== null ? 'pointer' : 'default' }}
    >
      <canvas
        ref={canvasRef}
        onMouseMove={handleMouseMove}
        onClick={handleClick}
        className="w-full h-full"
      />

      {/* Pin 1 selection hint */}
      {pin1Required && (
        <div className="absolute top-4 left-4 bg-warning/20 border border-warning/50 rounded-lg px-3 py-2">
          <p className="text-sm text-warning">
            Click on a pad to select Pin 1
          </p>
        </div>
      )}

      {/* Hover tooltip */}
      {hoveredPad !== null && footprint?.pads?.[hoveredPad] && (
        <div className="absolute bottom-4 left-4 bg-bg-tertiary border border-text-secondary/30 rounded-lg px-3 py-2">
          <PadTooltip pad={footprint.pads[hoveredPad]} index={hoveredPad} />
        </div>
      )}

      {/* Scale indicator */}
      <div className="absolute bottom-4 right-4 text-xs text-text-secondary">
        Scale: {scale.toFixed(2)}x
      </div>
    </div>
  )
}

/**
 * Draw background grid.
 */
function drawGrid(ctx, width, height, scale, offset) {
  const MM_TO_PX = 50
  const gridSize = 1 // 1mm grid
  const gridPx = gridSize * MM_TO_PX * scale

  ctx.strokeStyle = '#1a1918'
  ctx.lineWidth = 1

  // Vertical lines
  const startX = offset.x % gridPx
  for (let x = startX; x < width; x += gridPx) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }

  // Horizontal lines
  const startY = offset.y % gridPx
  for (let y = startY; y < height; y += gridPx) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
}

/**
 * Draw origin crosshair.
 */
function drawOrigin(ctx, scale, offset) {
  const size = 10

  ctx.strokeStyle = '#656462'
  ctx.lineWidth = 1

  // Horizontal
  ctx.beginPath()
  ctx.moveTo(offset.x - size, offset.y)
  ctx.lineTo(offset.x + size, offset.y)
  ctx.stroke()

  // Vertical
  ctx.beginPath()
  ctx.moveTo(offset.x, offset.y - size)
  ctx.lineTo(offset.x, offset.y + size)
  ctx.stroke()
}

/**
 * Draw spacing dimensions between pads.
 * Shows X and Y pitch measurements outside the component bounds.
 */
function drawSpacingDimensions(ctx, pads, scale, offset, MM_TO_PX) {
  if (!pads || pads.length < 2) return

  // Calculate bounding box of all pads (in mm)
  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity

  pads.forEach(pad => {
    const halfW = (pad.width || 0.5) / 2
    const halfH = (pad.height || 0.5) / 2
    minX = Math.min(minX, pad.x - halfW)
    maxX = Math.max(maxX, pad.x + halfW)
    minY = Math.min(minY, pad.y - halfH)
    maxY = Math.max(maxY, pad.y + halfH)
  })

  const bounds = { minX, maxX, minY, maxY }

  // Find X spacing (horizontal pitch)
  const xSpacing = findPadSpacing(pads, 'x')
  // Find Y spacing (vertical pitch)
  const ySpacing = findPadSpacing(pads, 'y')

  ctx.strokeStyle = '#60a5fa' // Blue for dimensions
  ctx.fillStyle = '#60a5fa'
  ctx.lineWidth = 1
  ctx.font = `${Math.max(10, 11 * scale)}px Inter, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'

  // Draw X dimension if found (above all pads)
  if (xSpacing) {
    const { pad1, pad2, distance } = xSpacing
    drawDimensionLine(ctx, pad1, pad2, distance, 'x', scale, offset, MM_TO_PX, bounds)
  }

  // Draw Y dimension if found (to the left of all pads)
  if (ySpacing) {
    const { pad1, pad2, distance } = ySpacing
    drawDimensionLine(ctx, pad1, pad2, distance, 'y', scale, offset, MM_TO_PX, bounds)
  }
}

/**
 * Find representative pad spacing in a given direction.
 */
function findPadSpacing(pads, direction) {
  const tolerance = 0.1 // mm tolerance for "same" position
  const spacings = []

  for (let i = 0; i < pads.length; i++) {
    for (let j = i + 1; j < pads.length; j++) {
      const p1 = pads[i]
      const p2 = pads[j]

      if (direction === 'x') {
        // Check if pads are in same row (similar Y)
        if (Math.abs(p1.y - p2.y) < tolerance) {
          const dist = Math.abs(p1.x - p2.x)
          if (dist > 0.1) { // Minimum distance
            spacings.push({
              pad1: p1,
              pad2: p2,
              distance: dist
            })
          }
        }
      } else {
        // Check if pads are in same column (similar X)
        if (Math.abs(p1.x - p2.x) < tolerance) {
          const dist = Math.abs(p1.y - p2.y)
          if (dist > 0.1) {
            spacings.push({
              pad1: p1,
              pad2: p2,
              distance: dist
            })
          }
        }
      }
    }
  }

  if (spacings.length === 0) return null

  // Find the most common (smallest) spacing - likely the pitch
  spacings.sort((a, b) => a.distance - b.distance)

  // Return the smallest spacing (typical pitch)
  return spacings[0]
}

/**
 * Draw a dimension line between two pads.
 * Positions dimension lines outside the component bounds.
 */
function drawDimensionLine(ctx, pad1, pad2, distance, direction, scale, offset, MM_TO_PX, bounds) {
  // Convert pad positions to canvas coordinates
  const x1 = offset.x + pad1.x * MM_TO_PX * scale
  const y1 = offset.y - pad1.y * MM_TO_PX * scale
  const x2 = offset.x + pad2.x * MM_TO_PX * scale
  const y2 = offset.y - pad2.y * MM_TO_PX * scale

  // Convert bounds to canvas coordinates
  const boundsTop = offset.y - bounds.maxY * MM_TO_PX * scale    // maxY is top in mm
  const boundsBottom = offset.y - bounds.minY * MM_TO_PX * scale // minY is bottom in mm
  const boundsLeft = offset.x + bounds.minX * MM_TO_PX * scale
  const boundsRight = offset.x + bounds.maxX * MM_TO_PX * scale

  const dimOffset = 25 * scale // Offset from bounds
  const extensionGap = 5

  if (direction === 'x') {
    // Horizontal dimension - draw ABOVE all pads (outside bounds)
    const dimY = boundsTop - dimOffset

    // Extension lines from pads up to dimension line
    ctx.beginPath()
    ctx.moveTo(x1, boundsTop - extensionGap)
    ctx.lineTo(x1, dimY - extensionGap)
    ctx.moveTo(x2, boundsTop - extensionGap)
    ctx.lineTo(x2, dimY - extensionGap)
    ctx.stroke()

    // Dimension line with arrows
    ctx.beginPath()
    ctx.moveTo(x1, dimY)
    ctx.lineTo(x2, dimY)
    ctx.stroke()

    // Arrows
    drawArrow(ctx, x1, dimY, 'right')
    drawArrow(ctx, x2, dimY, 'left')

    // Text
    const textX = (x1 + x2) / 2
    ctx.fillStyle = '#141311'
    ctx.fillRect(textX - 25, dimY - 8, 50, 16)
    ctx.fillStyle = '#60a5fa'
    ctx.fillText(`${distance.toFixed(2)}mm`, textX, dimY)

  } else {
    // Vertical dimension - draw to the LEFT of all pads (outside bounds)
    const dimX = boundsLeft - dimOffset

    // Extension lines from pads to dimension line
    ctx.beginPath()
    ctx.moveTo(boundsLeft - extensionGap, y1)
    ctx.lineTo(dimX - extensionGap, y1)
    ctx.moveTo(boundsLeft - extensionGap, y2)
    ctx.lineTo(dimX - extensionGap, y2)
    ctx.stroke()

    // Dimension line with arrows
    ctx.beginPath()
    ctx.moveTo(dimX, y1)
    ctx.lineTo(dimX, y2)
    ctx.stroke()

    // Arrows
    drawArrow(ctx, dimX, y1, 'down')
    drawArrow(ctx, dimX, y2, 'up')

    // Text (rotated)
    const textY = (y1 + y2) / 2
    ctx.save()
    ctx.translate(dimX, textY)
    ctx.rotate(-Math.PI / 2)
    ctx.fillStyle = '#141311'
    ctx.fillRect(-25, -8, 50, 16)
    ctx.fillStyle = '#60a5fa'
    ctx.fillText(`${distance.toFixed(2)}mm`, 0, 0)
    ctx.restore()
  }
}

/**
 * Draw an arrow head.
 */
function drawArrow(ctx, x, y, direction) {
  const size = 5
  ctx.beginPath()

  switch (direction) {
    case 'left':
      ctx.moveTo(x, y)
      ctx.lineTo(x + size, y - size / 2)
      ctx.lineTo(x + size, y + size / 2)
      break
    case 'right':
      ctx.moveTo(x, y)
      ctx.lineTo(x - size, y - size / 2)
      ctx.lineTo(x - size, y + size / 2)
      break
    case 'up':
      ctx.moveTo(x, y)
      ctx.lineTo(x - size / 2, y + size)
      ctx.lineTo(x + size / 2, y + size)
      break
    case 'down':
      ctx.moveTo(x, y)
      ctx.lineTo(x - size / 2, y - size)
      ctx.lineTo(x + size / 2, y - size)
      break
  }

  ctx.closePath()
  ctx.fill()
}

/**
 * Calculate outline bounds from pads with clearance.
 * Returns the outline rectangle in mm coordinates.
 */
function calculateOutlineBounds(pads, clearance = 0.3) {
  if (!pads || pads.length === 0) return null

  let minX = Infinity, maxX = -Infinity
  let minY = Infinity, maxY = -Infinity

  pads.forEach(pad => {
    const halfW = (pad.width || 0.5) / 2
    const halfH = (pad.height || 0.5) / 2
    minX = Math.min(minX, pad.x - halfW)
    maxX = Math.max(maxX, pad.x + halfW)
    minY = Math.min(minY, pad.y - halfH)
    maxY = Math.max(maxY, pad.y + halfH)
  })

  // Add clearance
  return {
    minX: minX - clearance,
    maxX: maxX + clearance,
    minY: minY - clearance,
    maxY: maxY + clearance,
    width: (maxX - minX) + 2 * clearance,
    height: (maxY - minY) + 2 * clearance,
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
  }
}

/**
 * Draw component outline.
 * Calculates bounds from pads to ensure outline surrounds all pads.
 */
function drawOutline(ctx, outline, scale, offset, MM_TO_PX, pads) {
  // Calculate bounds from pads with clearance
  const bounds = calculateOutlineBounds(pads, 0.3) // 0.3mm clearance

  if (!bounds) {
    // Fallback to outline dimensions if no pads
    const w = (outline?.width || 4) * MM_TO_PX * scale
    const h = (outline?.height || 4) * MM_TO_PX * scale

    ctx.strokeStyle = '#e6fb53'
    ctx.lineWidth = 2
    ctx.setLineDash([5, 5])
    ctx.strokeRect(offset.x - w / 2, offset.y - h / 2, w, h)
    ctx.setLineDash([])
    return
  }

  // Convert bounds to canvas coordinates
  const x1 = offset.x + bounds.minX * MM_TO_PX * scale
  const y1 = offset.y - bounds.maxY * MM_TO_PX * scale // maxY is top in mm, but lower Y in canvas
  const w = bounds.width * MM_TO_PX * scale
  const h = bounds.height * MM_TO_PX * scale

  ctx.strokeStyle = '#e6fb53'
  ctx.lineWidth = 2
  ctx.setLineDash([5, 5])

  ctx.strokeRect(x1, y1, w, h)

  ctx.setLineDash([])
}

/**
 * Draw a single pad.
 */
function drawPad(ctx, pad, index, scale, offset, MM_TO_PX, isPin1, isHovered, pin1Required, outlineBounds) {
  const x = offset.x + pad.x * MM_TO_PX * scale
  const y = offset.y - pad.y * MM_TO_PX * scale // Flip Y
  const w = (pad.width || 0.5) * MM_TO_PX * scale
  const h = (pad.height || 0.5) * MM_TO_PX * scale

  // Pad color based on state
  let fillColor = '#4a90a4' // Default blue
  if (pad.pad_type === 'th') {
    fillColor = '#a4904a' // Gold for through-hole
  }
  if (isPin1) {
    fillColor = '#e6fb53' // Accent for Pin 1
  }
  if (isHovered && pin1Required) {
    fillColor = '#e6fb53'
    ctx.globalAlpha = 0.8
  }

  // Draw pad shape
  ctx.fillStyle = fillColor

  if (pad.shape === 'round' || pad.shape === 'circular') {
    ctx.beginPath()
    ctx.arc(x, y, Math.min(w, h) / 2, 0, Math.PI * 2)
    ctx.fill()
  } else if (pad.shape === 'oval') {
    ctx.beginPath()
    ctx.ellipse(x, y, w / 2, h / 2, 0, 0, Math.PI * 2)
    ctx.fill()
  } else {
    // Rectangular (default)
    ctx.fillRect(x - w / 2, y - h / 2, w, h)
  }

  ctx.globalAlpha = 1

  // Draw drill hole for TH pads
  if (pad.pad_type === 'th' && pad.drill) {
    const drillD = (pad.drill.diameter || 0.3) * MM_TO_PX * scale
    ctx.fillStyle = '#141311'
    ctx.beginPath()
    ctx.arc(x, y, drillD / 2, 0, Math.PI * 2)
    ctx.fill()
  }

  // Draw pad label
  ctx.fillStyle = isPin1 ? '#0d0d0d' : '#f9f7f4'
  ctx.font = `${Math.max(10, 12 * scale)}px Inter, sans-serif`
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(pad.designator || String(index + 1), x, y)

  // Draw Pin 1 indicator - small solid dot OUTSIDE the outline
  if (isPin1 && outlineBounds) {
    const dotRadiusMM = 0.2 // Dot radius in mm
    const dotRadius = dotRadiusMM * MM_TO_PX * scale
    const gap = 0.25 // Gap between outline and dot in mm

    // Determine which corner of the outline is closest to Pin 1
    // Position the dot outside that corner
    const cornerX = pad.x <= outlineBounds.centerX ? outlineBounds.minX : outlineBounds.maxX
    const cornerY = pad.y <= outlineBounds.centerY ? outlineBounds.minY : outlineBounds.maxY

    // Direction from outline corner to outside
    const dirX = cornerX < outlineBounds.centerX ? -1 : 1
    const dirY = cornerY < outlineBounds.centerY ? -1 : 1

    // Position dot outside the outline corner
    const dotMmX = cornerX + dirX * (gap + dotRadiusMM)
    const dotMmY = cornerY + dirY * (gap + dotRadiusMM)

    // Convert to canvas coordinates
    const dotX = offset.x + dotMmX * MM_TO_PX * scale
    const dotY = offset.y - dotMmY * MM_TO_PX * scale // Flip Y

    // Draw filled dot
    ctx.fillStyle = '#e6fb53'
    ctx.beginPath()
    ctx.arc(dotX, dotY, dotRadius, 0, Math.PI * 2)
    ctx.fill()
  }
}

/**
 * Tooltip showing pad details.
 */
function PadTooltip({ pad, index }) {
  return (
    <div className="text-sm space-y-1">
      <div className="font-semibold text-text-primary">
        Pad {pad.designator || index + 1}
      </div>
      <div className="text-text-secondary text-xs space-y-0.5">
        <div>Position: ({pad.x?.toFixed(3)}, {pad.y?.toFixed(3)}) mm</div>
        <div>Size: {pad.width?.toFixed(3)} x {pad.height?.toFixed(3)} mm</div>
        <div>Type: {pad.pad_type?.toUpperCase()} {pad.shape}</div>
        {pad.drill && (
          <div>Drill: {pad.drill.diameter?.toFixed(3)} mm</div>
        )}
      </div>
    </div>
  )
}

export default PreviewCanvas
