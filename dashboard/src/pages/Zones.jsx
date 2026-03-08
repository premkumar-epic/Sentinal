import { useState, useEffect, useRef } from 'react'
import useStore, { API_BASE } from '../store/useStore'

export default function Zones() {
  const cameras = useStore((s) => s.cameras)
  const fetchCameras = useStore((s) => s.fetchCameras)

  const [selectedCam, setSelectedCam] = useState('')
  const [zones, setZones] = useState([])
  const [drawingMode, setDrawingMode] = useState(false)
  const [currentPoints, setCurrentPoints] = useState([])
  const [newZoneColor, setNewZoneColor] = useState('#FF0000')
  const [loading, setLoading] = useState(false)
  const [lastDoubleClickTime, setLastDoubleClickTime] = useState(0)

  const imgRef = useRef(null)

  // Fetch cameras on mount
  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  // When cameras load, select first one
  useEffect(() => {
    if (cameras.length > 0 && !selectedCam) {
      setSelectedCam(cameras[0].cam_id)
    }
  }, [cameras, selectedCam])

  // Fetch zones when camera changes
  useEffect(() => {
    if (selectedCam) {
      fetchZones()
    }
  }, [selectedCam])

  const fetchZones = async () => {
    try {
      const res = await fetch(
        `${API_BASE}/api/zones?cam_id=${selectedCam}`
      )
      if (res.ok) {
        setZones(await res.json())
      }
    } catch (e) {
      console.error('Failed to fetch zones:', e)
    }
  }

  // Compute centroid of polygon for label placement
  const computeCentroid = (polygon) => {
    if (polygon.length === 0) return [0, 0]
    const x = polygon.reduce((sum, p) => sum + p[0], 0) / polygon.length
    const y = polygon.reduce((sum, p) => sum + p[1], 0) / polygon.length
    return [x, y]
  }

  const handleSvgClick = (e) => {
    // Ignore clicks within 300ms of a dblclick
    if (Date.now() - lastDoubleClickTime < 300) {
      return
    }

    if (!drawingMode || !imgRef.current) return

    const rect = imgRef.current.getBoundingClientRect()
    const x = Math.round(e.clientX - rect.left)
    const y = Math.round(e.clientY - rect.top)

    setCurrentPoints([...currentPoints, [x, y]])
  }

  const handleSvgDoubleClick = (e) => {
    if (!drawingMode || currentPoints.length < 3) {
      setLastDoubleClickTime(Date.now())
      return
    }

    setLastDoubleClickTime(Date.now())

    const label = window.prompt('Zone label:', 'Restricted Area')
    if (!label || label.trim() === '') {
      return
    }

    saveZone(label.trim())
  }

  const saveZone = async (label) => {
    if (!selectedCam || currentPoints.length < 3) {
      alert('Need at least 3 points to create a zone')
      return
    }

    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/zones`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          label,
          cam_id: selectedCam,
          polygon: currentPoints,
          color: newZoneColor,
        }),
      })

      if (res.ok) {
        setCurrentPoints([])
        setDrawingMode(false)
        await fetchZones()
      } else {
        alert('Failed to create zone')
      }
    } catch (e) {
      console.error('Failed to save zone:', e)
      alert('Error creating zone')
    } finally {
      setLoading(false)
    }
  }

  const toggleZoneActive = async (zoneId, currentActive) => {
    try {
      const res = await fetch(`${API_BASE}/api/zones/${zoneId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active: !currentActive }),
      })

      if (res.ok) {
        await fetchZones()
      }
    } catch (e) {
      console.error('Failed to toggle zone:', e)
    }
  }

  const deleteZone = async (zoneId) => {
    if (!window.confirm('Delete this zone?')) return

    try {
      const res = await fetch(`${API_BASE}/api/zones/${zoneId}`, {
        method: 'DELETE',
      })

      if (res.ok) {
        await fetchZones()
      }
    } catch (e) {
      console.error('Failed to delete zone:', e)
    }
  }

  const pointsString = currentPoints
    .map((p) => `${p[0]},${p[1]}`)
    .join(' ')

  if (cameras.length === 0) {
    return (
      <div className="w-full h-screen bg-gray-900 flex items-center justify-center text-gray-100">
        <div className="text-center">
          <h2 className="text-2xl font-bold mb-2">No Cameras</h2>
          <p className="text-gray-400">Register cameras to create zones.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full min-h-screen bg-gray-900 p-6 text-gray-100">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold mb-4">Zone Editor</h1>

          {/* Camera selector + Draw Zone toggle */}
          <div className="flex gap-4 mb-6">
            <select
              value={selectedCam}
              onChange={(e) => {
                setSelectedCam(e.target.value)
                setDrawingMode(false)
                setCurrentPoints([])
              }}
              className="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-gray-100"
            >
              {cameras.map((cam) => (
                <option key={cam.cam_id} value={cam.cam_id}>
                  {cam.label || cam.cam_id}
                </option>
              ))}
            </select>

            <button
              onClick={() => {
                if (drawingMode) {
                  setCurrentPoints([])
                }
                setDrawingMode(!drawingMode)
              }}
              className={`px-4 py-2 rounded font-semibold transition-colors ${
                drawingMode
                  ? 'bg-yellow-600 hover:bg-yellow-700 text-black'
                  : 'bg-cyan-600 hover:bg-cyan-700 text-white'
              }`}
            >
              {drawingMode ? 'Cancel Drawing' : 'Draw Zone'}
            </button>

            {drawingMode && (
              <div className="flex gap-2 items-center">
                <label className="text-sm text-gray-400">Color:</label>
                <input
                  type="color"
                  value={newZoneColor}
                  onChange={(e) => setNewZoneColor(e.target.value)}
                  className="w-12 h-10 cursor-pointer rounded"
                />
              </div>
            )}
          </div>
        </div>

        {/* Camera feed with SVG overlay */}
        <div className="mb-6 rounded-lg overflow-hidden border border-gray-700">
          <div
            style={{
              position: 'relative',
              display: 'inline-block',
              width: '100%',
            }}
          >
            <img
              ref={imgRef}
              src={`${API_BASE}/api/stream/${selectedCam}`}
              alt="Camera feed"
              style={{
                display: 'block',
                maxWidth: '100%',
                width: '100%',
                height: 'auto',
              }}
              onError={(e) => {
                e.target.src = '/placeholder-camera.png'
              }}
            />

            {/* SVG overlay */}
            <svg
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                height: '100%',
                cursor: drawingMode ? 'crosshair' : 'default',
              }}
              onClick={handleSvgClick}
              onDoubleClick={handleSvgDoubleClick}
              className="border-0"
            >
              {/* Render existing zones */}
              {zones.map((zone) => {
                const polygon = zone.polygon || []
                if (polygon.length === 0) return null

                const pointsStr = polygon
                  .map((p) => `${p[0]},${p[1]}`)
                  .join(' ')
                const [cx, cy] = computeCentroid(polygon)

                return (
                  <g key={zone.zone_id}>
                    <polygon
                      points={pointsStr}
                      fill={zone.color}
                      fillOpacity="0.25"
                      stroke={zone.color}
                      strokeWidth="2"
                    />
                    <text
                      x={cx}
                      y={cy}
                      fill={zone.color}
                      fontSize="14"
                      fontWeight="bold"
                      textAnchor="middle"
                      dominantBaseline="middle"
                      pointerEvents="none"
                    >
                      {zone.label}
                    </text>
                  </g>
                )
              })}

              {/* Render in-progress zone being drawn */}
              {drawingMode && currentPoints.length > 0 && (
                <g>
                  <polyline
                    points={pointsString}
                    stroke="#FFD700"
                    strokeWidth="2"
                    fill="none"
                  />
                  {currentPoints.map((point, idx) => (
                    <circle
                      key={idx}
                      cx={point[0]}
                      cy={point[1]}
                      r="5"
                      fill="#FFD700"
                    />
                  ))}
                </g>
              )}
            </svg>
          </div>
        </div>

        {/* Drawing instructions */}
        {drawingMode && (
          <div className="mb-6 p-4 bg-yellow-900 text-yellow-100 rounded border border-yellow-700">
            <p className="text-sm">
              Click points on the feed to draw a polygon. Double-click to close
              and save. Minimum 3 points required.
            </p>
            {currentPoints.length > 0 && (
              <p className="text-sm mt-2">
                Points: {currentPoints.length}
              </p>
            )}
          </div>
        )}

        {/* Zones list */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Zones for {selectedCam}</h2>
          {zones.length === 0 ? (
            <p className="text-gray-400">No zones for this camera.</p>
          ) : (
            <div className="flex flex-wrap gap-4">
              {zones.map((zone) => (
                <div
                  key={zone.zone_id}
                  className="bg-gray-800 border border-gray-700 rounded p-4 flex items-center gap-3"
                >
                  {/* Color swatch */}
                  <div
                    className="w-6 h-6 rounded border border-gray-600 flex-shrink-0"
                    style={{ backgroundColor: zone.color }}
                  />

                  {/* Label */}
                  <div className="flex-1 min-w-0">
                    <p className="font-mono text-sm text-gray-100 truncate">
                      {zone.label}
                    </p>
                  </div>

                  {/* Active toggle */}
                  <label className="flex items-center gap-2 cursor-pointer flex-shrink-0">
                    <input
                      type="checkbox"
                      checked={zone.active}
                      onChange={() =>
                        toggleZoneActive(zone.zone_id, zone.active)
                      }
                      className="w-4 h-4"
                    />
                    <span className="text-xs text-gray-400">Active</span>
                  </label>

                  {/* Delete button */}
                  <button
                    onClick={() => deleteZone(zone.zone_id)}
                    className="px-3 py-1 bg-red-900 hover:bg-red-800 rounded text-sm text-gray-100 flex-shrink-0"
                  >
                    Delete
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
