import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../store/useStore'

const LIMIT = 50

export default function Events() {
  const [events, setEvents] = useState([])
  const [offset, setOffset] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(false)

  // Filters
  const [camId, setCamId] = useState('')
  const [alertType, setAlertType] = useState('')
  const [since, setSince] = useState('')

  // Modal
  const [selected, setSelected] = useState(null)

  const fetchEvents = useCallback(async (off = 0) => {
    setLoading(true)
    const params = new URLSearchParams({ limit: LIMIT + 1, offset: off })
    if (camId) params.set('cam_id', camId)
    if (alertType) params.set('alert_type', alertType)
    if (since) params.set('since', since)

    try {
      const res = await fetch(`${API_BASE}/api/events?${params}`)
      if (!res.ok) throw new Error(res.statusText)
      const data = await res.json()
      setHasMore(data.length > LIMIT)
      setEvents(data.slice(0, LIMIT))
      setOffset(off)
    } catch (err) {
      console.error('Failed to fetch events', err)
    } finally {
      setLoading(false)
    }
  }, [camId, alertType, since])

  useEffect(() => { fetchEvents(0) }, [fetchEvents])

  const applyFilters = (e) => { e.preventDefault(); fetchEvents(0) }

  return (
    <div style={s.root}>
      <h2 style={s.title}>Event Log</h2>

      {/* Filter bar */}
      <form onSubmit={applyFilters} style={s.filterBar}>
        <input
          style={s.input}
          placeholder="Camera ID"
          value={camId}
          onChange={(e) => setCamId(e.target.value)}
        />
        <select style={s.input} value={alertType} onChange={(e) => setAlertType(e.target.value)}>
          <option value="">All types</option>
          {['intrusion', 'weapon', 'loitering', 'crowding', 'violence', 'face_match'].map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <input
          style={s.input}
          type="datetime-local"
          value={since}
          onChange={(e) => setSince(e.target.value)}
          title="Since"
        />
        <button style={s.btn} type="submit">Filter</button>
        <button style={s.btnGhost} type="button" onClick={() => { setCamId(''); setAlertType(''); setSince('') }}>
          Clear
        </button>
      </form>

      {/* Table */}
      {loading ? (
        <p style={s.dim}>Loading…</p>
      ) : events.length === 0 ? (
        <p style={s.dim}>No events found.</p>
      ) : (
        <div style={s.tableWrap}>
          <table style={s.table}>
            <thead>
              <tr>
                {['Timestamp', 'Camera', 'Type', 'Zone', 'Name / ID', 'Snapshot'].map((h) => (
                  <th key={h} style={s.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {events.map((ev) => (
                <tr key={ev.id} style={s.tr} onClick={() => setSelected(ev)}>
                  <td style={s.td}>{ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '—'}</td>
                  <td style={s.td}>{ev.cam_id}</td>
                  <td style={{ ...s.td, color: typeColor(ev.alert_type) }}>{ev.alert_type}</td>
                  <td style={s.td}>{ev.zone_id || '—'}</td>
                  <td style={s.td}>{ev.name || (ev.global_ids?.[0] ?? '—')}</td>
                  <td style={s.td}>
                    {ev.snapshot_path ? (
                      <img
                        src={`${API_BASE}/api/snapshots/${ev.snapshot_path}`}
                        alt="snap"
                        style={s.thumb}
                      />
                    ) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      <div style={s.pagination}>
        <button
          style={offset === 0 ? s.btnDisabled : s.btn}
          disabled={offset === 0}
          onClick={() => fetchEvents(Math.max(0, offset - LIMIT))}
        >
          ← Prev
        </button>
        <span style={s.dim}>Showing {offset + 1}–{offset + events.length}</span>
        <button
          style={!hasMore ? s.btnDisabled : s.btn}
          disabled={!hasMore}
          onClick={() => fetchEvents(offset + LIMIT)}
        >
          Next →
        </button>
      </div>

      {/* Detail modal */}
      {selected && <EventModal event={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function EventModal({ event: ev, onClose }) {
  return (
    <div style={s.overlay} onClick={onClose}>
      <div style={s.modal} onClick={(e) => e.stopPropagation()}>
        <button style={s.closeBtn} onClick={onClose}>✕</button>
        <h3 style={s.modalTitle}>{ev.alert_type}</h3>

        {ev.snapshot_path && (
          <img
            src={`${API_BASE}/api/snapshots/${ev.snapshot_path}`}
            alt="snapshot"
            style={s.modalImg}
          />
        )}

        <table style={s.detailTable}>
          <tbody>
            {[
              ['ID', ev.id],
              ['Timestamp', ev.timestamp],
              ['Camera', ev.cam_id],
              ['Zone', ev.zone_id || '—'],
              ['Name', ev.name || '—'],
              ['Global IDs', (ev.global_ids || []).join(', ') || '—'],
              ['Track IDs', (ev.track_ids || []).join(', ') || '—'],
              ['Confidence', ev.confidence != null ? `${(ev.confidence * 100).toFixed(1)}%` : '—'],
            ].map(([k, v]) => (
              <tr key={k}>
                <td style={s.dtKey}>{k}</td>
                <td style={s.dtVal}>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function typeColor(type) {
  const map = { weapon: '#ff1744', intrusion: '#ff9100', loitering: '#ffea00', crowding: '#e040fb', violence: '#ff1744', face_match: '#00e676' }
  return map[type] || '#e0e0e0'
}

const s = {
  root: { padding: '16px', background: '#0d0d0d', minHeight: '100vh', color: '#e0e0e0', fontFamily: 'monospace' },
  title: { margin: '0 0 12px', color: '#00e5ff', fontSize: '1.1rem' },
  filterBar: { display: 'flex', gap: '8px', marginBottom: '12px', flexWrap: 'wrap', alignItems: 'center' },
  input: { background: '#1a1a1a', border: '1px solid #444', color: '#e0e0e0', padding: '4px 8px', borderRadius: '3px', fontSize: '0.8rem' },
  btn: { padding: '4px 12px', background: '#00e5ff', color: '#000', border: 'none', borderRadius: '3px', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 'bold' },
  btnGhost: { padding: '4px 12px', background: '#2a2a2a', color: '#aaa', border: '1px solid #444', borderRadius: '3px', cursor: 'pointer', fontSize: '0.8rem' },
  btnDisabled: { padding: '4px 12px', background: '#1a1a1a', color: '#555', border: '1px solid #333', borderRadius: '3px', cursor: 'default', fontSize: '0.8rem' },
  dim: { color: '#555', fontSize: '0.85rem' },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
  th: { padding: '6px 8px', background: '#1a1a1a', color: '#aaa', textAlign: 'left', borderBottom: '1px solid #333', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #222', cursor: 'pointer' },
  td: { padding: '5px 8px', verticalAlign: 'middle' },
  thumb: { width: '48px', height: '32px', objectFit: 'cover', borderRadius: '2px' },
  pagination: { display: 'flex', alignItems: 'center', gap: '16px', marginTop: '12px' },
  overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
  modal: { background: '#1a1a1a', border: '1px solid #444', borderRadius: '6px', padding: '24px', maxWidth: '600px', width: '90%', position: 'relative', maxHeight: '90vh', overflowY: 'auto' },
  closeBtn: { position: 'absolute', top: '8px', right: '12px', background: 'none', border: 'none', color: '#aaa', fontSize: '1.1rem', cursor: 'pointer' },
  modalTitle: { margin: '0 0 12px', color: '#00e5ff', fontSize: '1rem' },
  modalImg: { width: '100%', maxHeight: '300px', objectFit: 'contain', borderRadius: '4px', marginBottom: '12px' },
  detailTable: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
  dtKey: { color: '#777', padding: '3px 8px 3px 0', whiteSpace: 'nowrap', width: '120px' },
  dtVal: { color: '#e0e0e0', padding: '3px 0', wordBreak: 'break-all' },
}
