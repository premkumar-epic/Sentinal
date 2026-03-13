import React from 'react'

export default function ZoneOverlay({ zones, camWidth, camHeight, activeZoneIds }) {
  if (!camWidth || !camHeight) return null

  // Calculate centroid for label placement
  const computeCentroid = (polygon) => {
    if (!polygon || polygon.length === 0) return [0, 0]
    const x = polygon.reduce((sum, p) => sum + p[0], 0) / polygon.length
    const y = polygon.reduce((sum, p) => sum + p[1], 0) / polygon.length
    return [x, y]
  }

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
      }}
      viewBox={`0 0 ${camWidth} ${camHeight}`}
      preserveAspectRatio="none"
    >
      {zones.map((zone) => {
        const polygon = zone.polygon || []
        if (polygon.length === 0) return null

        const isTriggered = activeZoneIds?.has(zone.zone_id)
        const pointsStr = polygon.map((p) => `${p[0]},${p[1]}`).join(' ')
        const [cx, cy] = computeCentroid(polygon)

        // If triggered, use danger color, else use zone's defined color
        const baseColor = isTriggered ? '#ef4444' : zone.color
        const opacity = isTriggered ? 0.4 : 0.15

        return (
          <g key={zone.zone_id}>
            <polygon
              points={pointsStr}
              fill={baseColor}
              fillOpacity={opacity}
              stroke={baseColor}
              strokeWidth="2"
              strokeOpacity={isTriggered ? 1 : 0.6}
              style={{ transition: 'all 0.3s ease' }}
            />
            
            {/* High-vis label pill */}
            <g transform={`translate(${cx}, ${cy})`}>
              <rect
                x="-40"
                y="-10"
                width="80"
                height="20"
                rx="4"
                fill="rgba(0,0,0,0.7)"
                stroke={baseColor}
                strokeWidth="1"
              />
              <text
                fill="#fff"
                fontSize="10"
                fontWeight="900"
                textAnchor="middle"
                dominantBaseline="middle"
                style={{ textTransform: 'uppercase', letterSpacing: '0.5px' }}
              >
                {zone.label}
              </text>
            </g>
          </g>
        )
      })}
    </svg>
  )
}
