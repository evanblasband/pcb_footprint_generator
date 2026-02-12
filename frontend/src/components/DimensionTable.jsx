/**
 * Table showing extracted pad dimensions with confidence highlighting.
 * Yellow/orange highlighting for low-confidence values.
 */
function DimensionTable({ footprint, extractionResult }) {
  if (!footprint?.pads?.length) {
    return null
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-text-primary">
          Dimensions
        </h2>
        <span className="text-xs text-text-secondary">
          {footprint.pads.length} pad{footprint.pads.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-success" />
          <span className="text-text-secondary">High confidence</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-warning" />
          <span className="text-text-secondary">Medium</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-confidence-low" />
          <span className="text-text-secondary">Low</span>
        </div>
      </div>

      {/* Outline dimensions */}
      {footprint.outline && (
        <div className="bg-bg-tertiary rounded-lg p-3">
          <h3 className="text-sm font-medium text-text-primary mb-2">Outline</h3>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-text-secondary">Width:</span>
              <span className="ml-2 text-text-primary">
                {footprint.outline.width?.toFixed(3)} mm
              </span>
            </div>
            <div>
              <span className="text-text-secondary">Height:</span>
              <span className="ml-2 text-text-primary">
                {footprint.outline.height?.toFixed(3)} mm
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Pads table */}
      <div className="bg-bg-tertiary rounded-lg overflow-hidden">
        <div className="max-h-64 overflow-y-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-bg-secondary">
              <tr className="text-text-secondary text-left">
                <th className="px-3 py-2 font-medium">Pad</th>
                <th className="px-3 py-2 font-medium">X</th>
                <th className="px-3 py-2 font-medium">Y</th>
                <th className="px-3 py-2 font-medium">W</th>
                <th className="px-3 py-2 font-medium">H</th>
                <th className="px-3 py-2 font-medium">Type</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-bg-secondary">
              {footprint.pads.map((pad, index) => (
                <PadRow key={index} pad={pad} index={index} />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Warnings */}
      {extractionResult?.warnings?.length > 0 && (
        <div className="space-y-1">
          <h3 className="text-sm font-medium text-warning">Warnings</h3>
          <ul className="text-xs text-text-secondary space-y-1">
            {extractionResult.warnings.map((warning, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-warning">!</span>
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * Single row in the pads table.
 */
function PadRow({ pad, index }) {
  const confidence = pad.confidence || 0.8 // Default high confidence if not provided

  const getValueClass = (conf) => {
    if (conf >= 0.7) return 'text-text-primary'
    if (conf >= 0.5) return 'text-warning'
    return 'text-confidence-low'
  }

  const getBgClass = (conf) => {
    if (conf >= 0.7) return ''
    if (conf >= 0.5) return 'bg-warning/10'
    return 'bg-confidence-low/10'
  }

  return (
    <tr className={`hover:bg-bg-secondary/50 ${getBgClass(confidence)}`}>
      <td className="px-3 py-2 font-medium text-text-primary">
        {pad.designator || index + 1}
      </td>
      <td className={`px-3 py-2 ${getValueClass(confidence)}`}>
        {pad.x?.toFixed(3)}
      </td>
      <td className={`px-3 py-2 ${getValueClass(confidence)}`}>
        {pad.y?.toFixed(3)}
      </td>
      <td className={`px-3 py-2 ${getValueClass(confidence)}`}>
        {pad.width?.toFixed(3)}
      </td>
      <td className={`px-3 py-2 ${getValueClass(confidence)}`}>
        {pad.height?.toFixed(3)}
      </td>
      <td className="px-3 py-2 text-text-secondary text-xs">
        {formatPadType(pad.pad_type, pad.shape)}
      </td>
    </tr>
  )
}

/**
 * Format pad type for display.
 */
function formatPadType(padType, shape) {
  const typeLabel = padType === 'smd' ? 'SMD' : padType === 'th' ? 'TH' : padType
  const shapeLabel = shape ? ` ${shape.charAt(0).toUpperCase()}` : ''
  return `${typeLabel}${shapeLabel}`
}

export default DimensionTable
