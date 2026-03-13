import { useState, useEffect, useCallback } from 'react'
import { Filter, Search, Calendar, History, Camera, Shield, Eye, ChevronLeft, ChevronRight, X, Clock, MapPin, Download, Trash2 } from 'lucide-react'
import useStore, { API_BASE } from '../store/useStore'

const LIMIT = 50

export default function Events() {
  const token = useStore((s) => s.token)
  const fetchEventsStore = useStore((s) => s.fetchEvents)
  const clearEventsStore = useStore((s) => s.clearEvents)
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
      const data = await fetchEventsStore(params.toString())
      if (data) {
        setHasMore(data.length > LIMIT)
        setEvents(data.slice(0, LIMIT))
        setOffset(off)
      }
    } catch (err) {
      console.error('Data retrieval fault:', err)
    } finally {
      setLoading(false)
    }
  }, [camId, alertType, since, fetchEventsStore])

  useEffect(() => { fetchEvents(0) }, [fetchEvents])

  const applyFilters = (e) => { e.preventDefault(); fetchEvents(0) }

  const handleClear = async () => {
    if (!window.confirm('PERMANENT ACTION: Purge all intelligence records from the archive?')) return
    const success = await clearEventsStore()
    if (success) fetchEvents(0)
  }

  const exportCSV = () => {
    if (events.length === 0) return

    const headers = ['id', 'timestamp', 'cam_id', 'alert_type', 'zone_id', 'name', 'confidence']
    const rows = events.map((ev) => [
      ev.id,
      ev.timestamp || '',
      ev.cam_id,
      ev.alert_type || '',
      ev.zone_id || '',
      ev.name || '',
      ev.confidence || ''
    ])

    const csvContent = [
      headers.join(','),
      ...rows.map((row) =>
        row
          .map((cell) => (typeof cell === 'string' && cell.includes(',') ? `"${cell}"` : cell))
          .join(',')
      )
    ].join('\n')

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    link.setAttribute('href', url)
    link.setAttribute('download', 'sentinal_events.csv')
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>Intelligence Archive</h2>
          <p style={s.subtitle}>Query historical detection events and threat metadata</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            style={{ ...s.btnGhost, display: 'flex', alignItems: 'center', gap: '8px', height: '42px' }} 
            onClick={exportCSV} 
            disabled={events.length === 0}
          >
            <Download size={16} /> EXPORT CSV
          </button>
          <button 
            style={{ ...s.btnGhost, display: 'flex', alignItems: 'center', gap: '8px', height: '42px', color: 'var(--status-danger)', borderColor: 'rgba(244, 63, 94, 0.2)' }} 
            onClick={handleClear}
          >
            <Trash2 size={16} /> CLEAR LOG
          </button>
        </div>
      </header>

      {/* Filter Terminal */}
      <section style={s.filterTerminal}>
        <form onSubmit={applyFilters} style={s.filterGrid}>
          <div style={s.inputWrapper}>
            <Search size={14} style={s.inputIcon} />
            <input
              style={s.input}
              placeholder="FILTER BY NODE ID"
              value={camId}
              onChange={(e) => setCamId(e.target.value)}
            />
          </div>

          <div style={s.inputWrapper}>
            <Shield size={14} style={s.inputIcon} />
            <select style={s.select} value={alertType} onChange={(e) => setAlertType(e.target.value)}>
              <option value="">ALL CLASSIFICATIONS</option>
              {['intrusion', 'weapon', 'loitering', 'crowding', 'violence', 'face_match', 'identity_registered'].map((t) => (
                <option key={t} value={t}>{t.toUpperCase().replace('_', ' ')}</option>
              ))}
            </select>
          </div>

          <div style={s.inputWrapper}>
            <Calendar size={14} style={s.inputIcon} />
            <input
              style={s.input}
              type="datetime-local"
              value={since}
              onChange={(e) => setSince(e.target.value)}
            />
          </div>

          <button style={s.btnPrimary} type="submit">
            <Filter size={14} /> EXECUTE QUERY
          </button>

          <button style={s.btnGhost} type="button" onClick={() => { setCamId(''); setAlertType(''); setSince('') }}>
            RESET
          </button>
        </form>
      </section>

      {/* Data Grid */}
      <section style={s.dataCard}>
        {loading ? (
          <div style={s.loadingState}>SYNCHRONIZING ARCHIVE...</div>
        ) : events.length === 0 ? (
          <div style={s.emptyState}>NO RECORDS MATCHING CURRENT CRITERIA</div>
        ) : (
          <div style={s.tableWrap}>
            <table style={s.table}>
              <thead>
                <tr>
                  {['TIMESTAMP', 'ORIGIN NODE', 'CLASSIFICATION', 'ZONE', 'IDENTIFIER', 'EVIDENCE'].map((h) => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {events.map((ev) => (
                  <tr key={ev.id} style={s.tr} onClick={() => setSelected(ev)}>
                    <td style={s.td}>
                      <div style={s.timeCol}>
                        <Clock size={12} color="var(--text-dim)" />
                        {ev.timestamp ? (
                          <>
                            <span style={{ whiteSpace: 'nowrap' }}>{new Date(ev.timestamp).toLocaleDateString([], { month: 'short', day: 'numeric' })}</span>
                            <span style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>{new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}</span>
                          </>
                        ) : '—'}
                      </div>
                    </td>
                    <td style={s.td} className="mono">{ev.cam_id}</td>
                    <td style={s.td}>
                      <span style={{ ...s.badge, color: typeColor(ev.alert_type), borderColor: typeColor(ev.alert_type), background: `${typeColor(ev.alert_type)}10` }}>
                        {ev.alert_type?.toUpperCase()}
                      </span>
                    </td>
                    <td style={s.td}>{ev.zone_id || '—'}</td>
                    <td style={s.td}>{ev.name || (ev.global_ids?.[0]?.slice(0, 8) ?? '—')}</td>
                    <td style={s.td}>
                      {ev.snapshot_path ? (
                        <div style={s.thumbContainer}>
                          <img
                            src={`${API_BASE}/api/snapshots/${ev.snapshot_path}${token ? `?token=${token}` : ''}`}
                            alt="EVIDENCE"
                            style={s.thumb}
                          />
                          <div style={s.thumbOverlay}><Eye size={12} /></div>
                        </div>
                      ) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination Console */}
        <div style={s.paginationConsole}>
          <button
            style={offset === 0 ? s.pagBtnDisabled : s.pagBtn}
            disabled={offset === 0}
            onClick={() => fetchEvents(Math.max(0, offset - LIMIT))}
          >
            <ChevronLeft size={16} /> PREVIOUS
          </button>
          <div style={s.pagInfo}>PAGE {Math.floor(offset / LIMIT) + 1} <span style={{ color: 'var(--text-dim)' }}>| RECORDS {offset + 1}–{offset + events.length}</span></div>
          <button
            style={!hasMore ? s.pagBtnDisabled : s.pagBtn}
            disabled={!hasMore}
            onClick={() => fetchEvents(offset + LIMIT)}
          >
            NEXT <ChevronRight size={16} />
          </button>
        </div>
      </section>

      {/* Investigation Modal */}
      {selected && <EventModal event={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}

function EventModal({ event: ev, onClose }) {
  const token = useStore((s) => s.token)
  return (
    <div style={s.modalOverlay} onClick={onClose}>
      <div style={s.modalContent} onClick={(e) => e.stopPropagation()}>
        <header style={s.modalHeader}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ ...s.headerDot, background: typeColor(ev.alert_type) }} />
            <h3 style={s.modalTitle}>EVENT INVESTIGATION: {ev.alert_type?.toUpperCase()}</h3>
          </div>
          <button style={s.closeBtn} onClick={onClose}><X size={20} /></button>
        </header>

        <div style={s.modalBody}>
          <div style={s.modalEvidence}>
            {ev.snapshot_path ? (
              <img
                src={`${API_BASE}/api/snapshots/${ev.snapshot_path}${token ? `?token=${token}` : ''}`}
                alt="FORENSIC CAPTURE"
                style={s.modalImg}
              />
            ) : (
              <div style={s.noEvidence}>NO FORENSIC CAPTURE AVAILABLE</div>
            )}
          </div>

          <div style={s.modalMeta}>
            <div style={s.metaGroup}>
              <div style={s.metaLabel}><Clock size={12} /> TEMPORAL DATA</div>
              <div style={s.metaValue}>{ev.timestamp}</div>
            </div>

            <div style={s.metaGrid}>
              <div style={s.metaGroup}>
                <div style={s.metaLabel}><Camera size={12} /> ORIGIN NODE</div>
                <div style={s.metaValue} className="mono">{ev.cam_id}</div>
              </div>
              <div style={s.metaGroup}>
                <div style={s.metaLabel}><MapPin size={12} /> SPATIAL ZONE</div>
                <div style={s.metaValue}>{ev.zone_id || 'GLOBAL'}</div>
              </div>
            </div>

            <div style={s.metaGroup}>
              <div style={s.metaLabel}><History size={12} /> ENTITY IDENTIFIERS</div>
              <div style={s.metaValue}>
                {ev.name && <div style={{ color: 'var(--accent-primary)', fontWeight: 800, marginBottom: '4px' }}>{ev.name}</div>}
                <div className="mono" style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                  UID: {(ev.global_ids || []).join(', ') || 'UNCLASSIFIED'}
                </div>
              </div>
            </div>

            <div style={s.metaGroup}>
              <div style={s.metaLabel}>CONFIDENCE METRIC</div>
              <div style={s.confidenceBarContainer}>
                <div style={{ ...s.confidenceBar, width: `${(ev.confidence || 0) * 100}%`, background: typeColor(ev.alert_type) }} />
                <span style={s.confidenceLabel}>{(ev.confidence * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function typeColor(type) {
  const map = {
    weapon: '#f43f5e',
    intrusion: '#f59e0b',
    loitering: '#8b5cf6',
    crowding: '#d946ef',
    violence: '#ef4444',
    face_match: '#10b981',
    identity_registered: '#3b82f6'
  }
  return map[type] || '#94a3b8'
}

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },

  filterTerminal: {
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-lg)', padding: '24px', boxShadow: 'var(--shadow-md)'
  },
  filterGrid: { display: 'flex', gap: '16px', flexWrap: 'wrap' },
  inputWrapper: { position: 'relative', display: 'flex', alignItems: 'center', flex: 1, minWidth: '200px' },
  inputIcon: { position: 'absolute', left: '16px', color: 'var(--text-dim)' },
  input: {
    width: '100%', background: 'var(--bg-app)', border: '1px solid var(--border-base)',
    color: 'var(--text-main)', padding: '12px 16px 12px 42px', borderRadius: 'var(--radius-md)',
    fontSize: '0.85rem', fontWeight: 600, outline: 'none', transition: 'border-color 0.2s'
  },
  select: {
    width: '100%', background: 'var(--bg-app)', border: '1px solid var(--border-base)',
    color: 'var(--text-main)', padding: '12px 16px 12px 42px', borderRadius: 'var(--radius-md)',
    fontSize: '0.85rem', fontWeight: 600, outline: 'none', transition: 'border-color 0.2s'
  },
  btnPrimary: {
    background: 'var(--accent-primary)', color: '#fff', border: 'none',
    padding: '0 24px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
    fontSize: '0.85rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px',
    boxShadow: '0 4px 12px var(--accent-soft)', transition: 'all 0.2s'
  },
  btnGhost: {
    background: 'transparent', color: 'var(--text-sub)',
    border: '1px solid var(--border-base)', padding: '0 24px',
    borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
    transition: 'all 0.2s'
  },

  dataCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-lg)', overflow: 'hidden', boxShadow: 'var(--shadow-md)'
  },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse' },
  th: {
    padding: '20px 24px', background: 'var(--bg-surface-raised)', color: 'var(--text-sub)',
    textAlign: 'left', fontSize: '0.75rem', fontWeight: 800, letterSpacing: '0.05em',
    borderBottom: '1px solid var(--border-bright)'
  },
  tr: { borderBottom: '1px solid var(--border-base)', cursor: 'pointer', transition: 'background 0.2s' },
  td: { padding: '16px 24px', fontSize: '0.85rem', color: 'var(--text-main)', verticalAlign: 'middle' },

  timeCol: { display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-sub)', fontSize: '0.8rem', fontWeight: 500 },
  badge: {
    padding: '4px 12px', borderRadius: '20px', fontSize: '0.7rem',
    fontWeight: 800, border: '1px solid', letterSpacing: '0.05em'
  },

  thumbContainer: {
    position: 'relative', width: '80px', height: '48px',
    borderRadius: 'var(--radius-sm)', overflow: 'hidden', border: '1px solid var(--border-bright)'
  },
  thumb: { width: '100%', height: '100%', objectFit: 'cover' },
  thumbOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.4)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    opacity: 0, transition: 'opacity 0.2s', color: '#fff'
  },

  paginationConsole: {
    padding: '20px 24px', display: 'flex', alignItems: 'center',
    justifyContent: 'space-between', borderTop: '1px solid var(--border-base)',
    background: 'var(--bg-surface)'
  },
  pagBtn: {
    background: 'var(--bg-app)', border: '1px solid var(--border-bright)',
    color: 'var(--text-main)', padding: '10px 20px', borderRadius: 'var(--radius-md)',
    cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px',
    transition: 'all 0.2s'
  },
  pagBtnDisabled: {
    background: 'transparent', border: '1px solid var(--border-base)',
    color: 'var(--text-dim)', padding: '10px 20px', borderRadius: 'var(--radius-md)',
    fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px', opacity: 0.5
  },
  pagInfo: { fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' },

  // Modal Styles
  modalOverlay: {
    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(8px)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', zIndex: 1000, padding: '40px',
    animation: 'fadeIn 0.2s ease-out'
  },
  modalContent: {
    background: 'var(--bg-surface)', border: '1px solid var(--border-bright)',
    borderRadius: 'var(--radius-lg)', maxWidth: '1000px', width: '100%',
    maxHeight: '90vh', display: 'flex', flexDirection: 'column',
    boxShadow: 'var(--shadow-lg)'
  },
  modalHeader: {
    padding: '24px 32px', borderBottom: '1px solid var(--border-base)',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between'
  },
  headerDot: { width: '10px', height: '10px', borderRadius: '50%' },
  modalTitle: { margin: 0, fontSize: '1rem', fontWeight: 800, letterSpacing: '0.05em', color: 'var(--text-main)' },
  closeBtn: { background: 'transparent', border: 'none', color: 'var(--text-sub)', cursor: 'pointer', padding: '4px', transition: 'color 0.2s' },

  modalBody: { display: 'grid', gridTemplateColumns: '1.2fr 400px', flex: 1, overflow: 'hidden' },
  modalEvidence: { background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' },
  modalImg: { maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', boxShadow: '0 0 40px rgba(0,0,0,0.5)', borderRadius: 'var(--radius-md)' },
  noEvidence: { color: 'var(--text-dim)', fontSize: '0.85rem', letterSpacing: '1px', fontWeight: 600 },

  modalMeta: { padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px', borderLeft: '1px solid var(--border-base)', overflowY: 'auto' },
  metaGroup: { display: 'flex', flexDirection: 'column', gap: '8px' },
  metaLabel: { fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-dim)', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: '8px' },
  metaValue: { fontSize: '0.95rem', color: 'var(--text-main)', lineHeight: '1.5', fontWeight: 500 },
  metaGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' },

  confidenceBarContainer: { position: 'relative', height: '28px', background: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', overflow: 'hidden', display: 'flex', alignItems: 'center', border: '1px solid var(--border-base)' },
  confidenceBar: { position: 'absolute', top: 0, left: 0, bottom: 0, transition: 'width 1s cubic-bezier(0.4, 0, 0.2, 1)' },
  confidenceLabel: { position: 'relative', zIndex: 1, marginLeft: '12px', fontSize: '0.8rem', fontWeight: 800, color: '#fff', textShadow: '0 1px 3px rgba(0,0,0,0.6)' },

  loadingState: { padding: '120px', textAlign: 'center', color: 'var(--text-dim)', letterSpacing: '0.1em', fontSize: '0.9rem', fontWeight: 600 },
  emptyState: { padding: '120px', textAlign: 'center', color: 'var(--text-dim)', letterSpacing: '0.05em', fontSize: '0.9rem', fontWeight: 600 },
}
