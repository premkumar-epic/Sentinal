import { User } from 'lucide-react'

export default function PersonBadge({ name, globalId, sightingCount, lastCam }) {
  const displayName = name || `Unknown #${globalId?.slice(0, 6) || '?'}`

  return (
    <div style={s.badge}>
      <User size={14} style={{ marginRight: '4px' }} />
      <span style={s.name}>{displayName}</span>
      {sightingCount > 0 && (
        <span style={s.meta}>· {sightingCount} sighting{sightingCount !== 1 ? 's' : ''}</span>
      )}
      {lastCam && (
        <span style={s.meta}>· {lastCam}</span>
      )}
    </div>
  )
}

const s = {
  badge: {
    display: 'inline-flex',
    alignItems: 'center',
    background: '#2a2a2a',
    border: '1px solid #444',
    borderRadius: '12px',
    padding: '2px 8px',
    fontSize: '0.75rem',
    color: '#e0e0e0',
    whiteSpace: 'nowrap',
    gap: '4px',
  },
  name: {
    fontWeight: '500',
  },
  meta: {
    color: '#999',
  },
}
