/**
 * ZoneOverlay — absolutely-positioned SVG that draws zone polygons over a camera feed.
 *
 * Props:
 *   zones        — array of zone objects {zone_id, label, polygon, color, active}
 *   camWidth     — pixel width of the camera feed image
 *   camHeight    — pixel height of the camera feed image
 *   activeZoneIds — Set of zone_id strings currently triggered (red fill)
 */
export default function ZoneOverlay({ zones = [], camWidth, camHeight, activeZoneIds = new Set() }) {
  if (!camWidth || !camHeight || zones.length === 0) return null

  return (
    <svg
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: camWidth,
        height: camHeight,
        pointerEvents: 'none',
      }}
      viewBox={`0 0 ${camWidth} ${camHeight}`}
    >
      {zones.filter((z) => z.active).map((zone) => {
        const triggered = activeZoneIds.has(zone.zone_id)
        const strokeColor = triggered ? '#ff1744' : zone.color
        const fillColor = triggered ? 'rgba(255,23,68,0.30)' : hexToRgba(zone.color, 0.20)

        const points = zone.polygon.map(([x, y]) => `${x},${y}`).join(' ')

        // Centroid for label
        const cx = zone.polygon.reduce((s, [x]) => s + x, 0) / zone.polygon.length
        const cy = zone.polygon.reduce((s, [, y]) => s + y, 0) / zone.polygon.length

        return (
          <g key={zone.zone_id}>
            <polygon
              points={points}
              fill={fillColor}
              stroke={strokeColor}
              strokeWidth={2}
              strokeLinejoin="round"
            />
            <text
              x={cx}
              y={cy}
              fill={strokeColor}
              fontSize={12}
              textAnchor="middle"
              dominantBaseline="middle"
              style={{ fontFamily: 'monospace', fontWeight: 'bold' }}
            >
              {zone.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

function hexToRgba(hex, alpha) {
  const h = hex.replace('#', '')
  const r = parseInt(h.slice(0, 2), 16)
  const g = parseInt(h.slice(2, 4), 16)
  const b = parseInt(h.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
