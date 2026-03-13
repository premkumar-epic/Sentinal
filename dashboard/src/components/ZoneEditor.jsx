import { useState, useRef, useEffect } from 'react'

export default function ZoneEditor({ cameraId, streamUrl, existingZone, onSave, onCancel }) {
  const [points, setPoints] = useState(existingZone?.polygon || [])
  const [color, setColor] = useState(existingZone?.color || '#FF0000')
  const [label, setLabel] = useState(existingZone?.label || '')
  const [draggingIdx, setDraggingIdx] = useState(null)
  const [lastClickTime, setLastClickTime] = useState(0)

  const imgRef = useRef(null)
  const svgRef = useRef(null)

  const handleSvgClick = (e) => {
    const now = Date.now()
    if (now - lastClickTime < 300) {
      setLastClickTime(0)
      return
    }
    setLastClickTime(now)

    if (!imgRef.current || !svgRef.current) return

    const svgRect = svgRef.current.getBoundingClientRect()
    const x = Math.round(e.clientX - svgRect.left)
    const y = Math.round(e.clientY - svgRect.top)

    setPoints([...points, [x, y]])
  }

  const handleSvgDoubleClick = (e) => {
    if (points.length < 3) {
      setLastClickTime(0)
      return
    }
    setLastClickTime(0)

    if (!label.trim()) {
      alert('Please enter a zone label before saving')
      return
    }

    saveZone()
  }

  const handleVertexMouseDown = (idx, e) => {
    e.preventDefault()
    e.stopPropagation()
    setDraggingIdx(idx)
  }

  const handleSvgMouseMove = (e) => {
    if (draggingIdx === null || !svgRef.current) return

    const svgRect = svgRef.current.getBoundingClientRect()
    const x = Math.round(e.clientX - svgRect.left)
    const y = Math.round(e.clientY - svgRect.top)

    const newPoints = [...points]
    newPoints[draggingIdx] = [x, y]
    setPoints(newPoints)
  }

  const handleSvgMouseUp = () => {
    setDraggingIdx(null)
  }

  const saveZone = () => {
    if (points.length < 3) {
      alert('Zone requires at least 3 vertices')
      return
    }

    if (!imgRef.current) return

    const rect = imgRef.current.getBoundingClientRect()
    const scaleX =
      imgRef.current.naturalWidth > 0 ? imgRef.current.naturalWidth / rect.width : 1
    const scaleY =
      imgRef.current.naturalHeight > 0
        ? imgRef.current.naturalHeight / rect.height
        : 1

    const scaled = points.map(([x, y]) => [
      Math.round(x * scaleX),
      Math.round(y * scaleY),
    ])

    onSave({ label: label.trim(), color, polygon: scaled })
  }

  const handleClear = () => {
    setPoints([])
  }

  const pointsString = points.map((p) => `${p[0]},${p[1]}`).join(' ')

  const styles = {
    container: {
      position: 'relative',
      background: '#000',
      borderRadius: '8px',
      overflow: 'hidden',
      aspectRatio: '16 / 9',
    },
    feedContainer: {
      width: '100%',
      height: '100%',
      position: 'relative',
    },
    feed: {
      width: '100%',
      height: '100%',
      display: 'block',
      objectFit: 'contain',
    },
    svg: {
      position: 'absolute',
      top: 0,
      left: 0,
      width: '100%',
      height: '100%',
      cursor: 'crosshair',
    },
    toolbar: {
      display: 'flex',
      gap: '12px',
      alignItems: 'center',
      padding: '16px',
      background: '#1a1a1a',
      flexWrap: 'wrap',
    },
    labelInput: {
      background: '#0d0d0d',
      border: '1px solid #333',
      color: '#e2e8f0',
      padding: '8px 12px',
      borderRadius: '6px',
      outline: 'none',
      fontSize: '0.85rem',
      flex: '1',
      minWidth: '150px',
    },
    colorInput: {
      width: '40px',
      height: '40px',
      border: 'none',
      borderRadius: '6px',
      cursor: 'pointer',
      background: 'none',
    },
    btn: {
      border: 'none',
      padding: '8px 16px',
      borderRadius: '6px',
      cursor: 'pointer',
      fontSize: '0.85rem',
      fontWeight: '700',
      transition: 'all 0.2s',
    },
    btnSave: {
      background: '#00e5ff',
      color: '#000',
      border: 'none',
    },
    btnCancel: {
      background: 'transparent',
      color: '#94a3b8',
      border: '1px solid #333',
    },
    btnClear: {
      background: 'rgba(244,63,94,0.1)',
      color: '#f43f5e',
      border: '1px solid rgba(244,63,94,0.2)',
    },
    hint: {
      color: '#00e5ff',
      fontSize: '0.75rem',
      fontWeight: '700',
      whiteSpace: 'nowrap',
    },
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={styles.container}>
        <div style={styles.feedContainer}>
          <img
            ref={imgRef}
            src={streamUrl}
            alt="Zone editor feed"
            style={styles.feed}
            onError={(e) => {
              e.target.src =
                'https://via.placeholder.com/1280x720?text=FEED+OFFLINE'
            }}
          />

          <svg
            ref={svgRef}
            style={styles.svg}
            onClick={handleSvgClick}
            onDoubleClick={handleSvgDoubleClick}
            onMouseMove={handleSvgMouseMove}
            onMouseUp={handleSvgMouseUp}
            onMouseLeave={handleSvgMouseUp}
          >
            {points.length > 0 && (
              <g>
                {points.length > 1 && (
                  <polyline
                    points={pointsString}
                    stroke={color}
                    strokeWidth="2"
                    fill="none"
                    opacity="0.8"
                  />
                )}
                {points.map((p, i) => (
                  <circle
                    key={i}
                    cx={p[0]}
                    cy={p[1]}
                    r="6"
                    fill={color}
                    stroke="#fff"
                    strokeWidth="2"
                    style={{ cursor: 'grab' }}
                    onMouseDown={(e) => handleVertexMouseDown(i, e)}
                  />
                ))}
              </g>
            )}
          </svg>
        </div>
      </div>

      <div style={styles.toolbar}>
        <input
          type="text"
          placeholder="Zone label"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          style={styles.labelInput}
        />

        <input
          type="color"
          value={color}
          onChange={(e) => setColor(e.target.value)}
          style={styles.colorInput}
          title="Zone color"
        />

        <button
          onClick={saveZone}
          style={{ ...styles.btn, ...styles.btnSave }}
          disabled={points.length < 3}
          title={points.length < 3 ? 'Minimum 3 vertices required' : 'Save zone'}
        >
          SAVE
        </button>

        <button
          onClick={onCancel}
          style={{ ...styles.btn, ...styles.btnCancel }}
          title="Cancel editing"
        >
          CANCEL
        </button>

        <button
          onClick={handleClear}
          style={{ ...styles.btn, ...styles.btnClear }}
          title="Clear all vertices"
        >
          CLEAR
        </button>

        <div style={styles.hint}>VERTICES: {points.length}</div>
      </div>
    </div>
  )
}
