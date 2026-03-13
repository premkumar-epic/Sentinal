import { useState, useEffect, useCallback } from 'react'
import { Shield, Plus, X, Trash2, Camera, Info } from 'lucide-react'
import useStore, { API_BASE } from '../store/useStore'
import ZoneEditor from '../components/ZoneEditor'

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },

  mainGrid: { display: 'grid', gridTemplateColumns: '1fr 340px', gap: '32px', minHeight: '600px' },

  editorCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-lg)', padding: '32px', display: 'flex',
    flexDirection: 'column', gap: '24px', boxShadow: 'var(--shadow-md)'
  },

  toolbar: { display: 'flex', gap: '16px', alignItems: 'center' },
  select: {
    padding: '12px 16px', background: 'var(--bg-app)',
    border: '1px solid var(--border-base)', color: 'var(--text-main)',
    borderRadius: 'var(--radius-md)', fontSize: '0.85rem', outline: 'none',
    transition: 'border-color 0.2s', fontWeight: 500
  },
  btn: {
    padding: '12px 24px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
    fontSize: '0.85rem', fontWeight: 700, border: 'none',
    display: 'flex', alignItems: 'center', gap: '8px', transition: 'all 0.2s'
  },
  btnDraw: { background: 'var(--accent-primary)', color: '#fff', boxShadow: '0 4px 12px var(--accent-soft)' },
  btnCancel: { background: 'rgba(244, 63, 94, 0.1)', color: 'var(--status-danger)', border: '1px solid rgba(244, 63, 94, 0.2)' },

  canvasContainer: {
    position: 'relative', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-md)', overflow: 'hidden', background: '#000',
    flex: 1, boxShadow: 'inset 0 0 40px rgba(0,0,0,0.5)'
  },
  feed: { width: '100%', height: '100%', display: 'block', objectFit: 'contain' },
  svg: { position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' },

  sidebar: { display: 'flex', flexDirection: 'column', gap: '24px' },
  sideCard: {
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-lg)', padding: '24px',
    boxShadow: 'var(--shadow-md)'
  },
  sideTitle: {
    margin: '0 0 20px', fontSize: '0.8rem', fontWeight: 800,
    color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '0.05em',
    display: 'flex', alignItems: 'center', gap: '8px'
  },

  zoneList: { display: 'flex', flexDirection: 'column', gap: '12px' },
  zoneItem: {
    background: 'var(--bg-app)', border: '1px solid var(--border-base)',
    borderRadius: 'var(--radius-md)', padding: '16px', transition: 'all 0.2s'
  },
  zoneHeader: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px' },
  colorSwatch: { width: '14px', height: '14px', borderRadius: '50%', border: '1px solid var(--border-bright)' },
  zoneLabel: { fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', flex: 1 },

  zoneActions: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-bright)', paddingTop: '12px' },
  activeToggle: {
    display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.75rem',
    fontWeight: 700, cursor: 'pointer', color: 'var(--text-sub)'
  },
  deleteBtn: {
    background: 'transparent', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', padding: '6px', borderRadius: '4px', transition: 'color 0.2s'
  },

  empty: { textAlign: 'center', padding: '60px 20px', color: 'var(--text-dim)', fontSize: '0.85rem', fontWeight: 500, letterSpacing: '0.05em' }
}

export default function Zones() {
  const token = useStore((s) => s.token)
  const cameras = useStore((s) => s.cameras)
  const fetchCameras = useStore((s) => s.fetchCameras)
  const fetchZonesStore = useStore((s) => s.fetchZones)
  const addZoneStore = useStore((s) => s.addZone)
  const updateZoneStore = useStore((s) => s.updateZone)
  const deleteZoneStore = useStore((s) => s.deleteZone)

  const [selectedCam, setSelectedCam] = useState('')
  const [zones, setZones] = useState([])
  const [showEditor, setShowEditor] = useState(false)

  const fetchZones = useCallback(async () => {
    if (selectedCam) {
      const data = await fetchZonesStore(selectedCam)
      setZones(data || [])
    }
  }, [selectedCam, fetchZonesStore])

  useEffect(() => {
    fetchCameras()
  }, [fetchCameras])

  useEffect(() => {
    if (cameras.length > 0 && !selectedCam) {
      setSelectedCam(cameras[0].cam_id)
    }
  }, [cameras, selectedCam])

  useEffect(() => {
    fetchZones()
  }, [fetchZones])

  const computeCentroid = (polygon) => {
    if (!polygon || polygon.length === 0) return [0, 0]
    const x = polygon.reduce((sum, p) => sum + p[0], 0) / polygon.length
    const y = polygon.reduce((sum, p) => sum + p[1], 0) / polygon.length
    return [x, y]
  }

  const toggleZoneActive = async (zoneId, currentActive) => {
    const success = await updateZoneStore(zoneId, { active: !currentActive })
    if (success) fetchZones()
  }

  const deleteZone = async (zoneId) => {
    if (!window.confirm('PERMANENT ACTION: Delete this detection zone?')) return
    const success = await deleteZoneStore(zoneId)
    if (success) fetchZones()
  }

  const handleEditorSave = async (zoneData) => {
    const success = await addZoneStore({
      ...zoneData,
      cam_id: selectedCam,
    })
    if (success) {
      setShowEditor(false)
      fetchZones()
    } else {
      alert('Initialization error. Zone registry rejected the payload.')
    }
  }

  if (cameras.length === 0) {
    return (
      <div style={s.root}>
        <div style={s.empty}>NO NODES AVAILABLE. REGISTER A CAMERA TO DEFINE DETECTION ZONES.</div>
      </div>
    )
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>Boundary Definition</h2>
          <p style={s.subtitle}>Configure spatial logic and alert parameters for system nodes</p>
        </div>
      </header>

      <div style={s.mainGrid}>
        {/* Editor Area */}
        <section style={s.editorCard}>
          <div style={s.toolbar}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-dim)', fontSize: '0.75rem', fontWeight: 700 }}>
              <Camera size={14} /> ACTIVE NODE:
            </div>
            <select
              value={selectedCam}
              onChange={(e) => {
                setSelectedCam(e.target.value)
                setShowEditor(false)
              }}
              style={s.select}
            >
              {cameras.map((cam) => (
                <option key={cam.cam_id} value={cam.cam_id}>
                  {cam.label || cam.cam_id}
                </option>
              ))}
            </select>

            <button
              onClick={() => setShowEditor(!showEditor)}
              style={{ ...s.btn, ...(showEditor ? s.btnCancel : s.btnDraw) }}
            >
              {showEditor ? <X size={16} /> : <Plus size={16} />}
              {showEditor ? 'ABORT DRAWING' : 'INITIALIZE BOUNDARY'}
            </button>
          </div>

          {showEditor ? (
            <ZoneEditor
              cameraId={selectedCam}
              streamUrl={`${API_BASE}/api/stream/${selectedCam}${token ? `?token=${token}` : ''}`}
              onSave={handleEditorSave}
              onCancel={() => setShowEditor(false)}
            />
          ) : (
            <div style={s.canvasContainer}>
              <img
                src={`${API_BASE}/api/stream/${selectedCam}${token ? `?token=${token}` : ''}`}
                alt="Calibration feed"
                style={s.feed}
                onError={(e) => { e.target.src = 'https://via.placeholder.com/1280x720?text=CALIBRATION+FEED+OFFLINE' }}
              />

              <svg style={s.svg}>
                {zones.map((zone) => {
                  const polygon = zone.polygon || []
                  if (polygon.length === 0) return null
                  const pointsStr = polygon.map((p) => `${p[0]},${p[1]}`).join(' ')
                  const [cx, cy] = computeCentroid(polygon)

                  return (
                    <g key={zone.zone_id}>
                      <polygon
                        points={pointsStr}
                        fill={zone.color}
                        fillOpacity={zone.active ? "0.2" : "0.05"}
                        stroke={zone.color}
                        strokeWidth="2"
                        strokeDasharray={zone.active ? "0" : "4"}
                        strokeOpacity={zone.active ? "1" : "0.3"}
                      />
                      <text
                        x={cx}
                        y={cy}
                        fill="#fff"
                        fontSize="10"
                        fontWeight="800"
                        textAnchor="middle"
                        dominantBaseline="middle"
                        pointerEvents="none"
                        style={{ textShadow: '0 1px 4px rgba(0,0,0,0.8)', opacity: zone.active ? 1 : 0.4, textTransform: 'uppercase' }}
                      >
                        {zone.label}
                      </text>
                    </g>
                  )
                })}
              </svg>
            </div>
          )}
        </section>

        {/* Sidebar Info */}
        <aside style={s.sidebar}>
          <div style={s.sideCard}>
            <h3 style={s.sideTitle}><Shield size={14} /> ACTIVE BOUNDARIES</h3>
            <div style={s.zoneList}>
              {zones.length === 0 ? (
                <div style={s.empty}>NO ZONES DEFINED FOR THIS NODE.</div>
              ) : (
                zones.map((zone) => (
                  <div key={zone.zone_id} style={{
                    ...s.zoneItem,
                    opacity: zone.active ? 1 : 0.6,
                    borderColor: zone.active ? 'var(--glass-border)' : 'transparent'
                  }}>
                    <div style={s.zoneHeader}>
                      <div style={{ ...s.colorSwatch, backgroundColor: zone.color }} />
                      <span style={s.zoneLabel}>{zone.label}</span>
                    </div>
                    <div style={s.zoneActions}>
                      <label style={s.activeToggle}>
                        <input
                          type="checkbox"
                          checked={zone.active}
                          onChange={() => toggleZoneActive(zone.zone_id, zone.active)}
                          style={{ margin: 0 }}
                        />
                        {zone.active ? 'MONITORING' : 'DISABLED'}
                      </label>
                      <button onClick={() => deleteZone(zone.zone_id)} style={s.deleteBtn}>
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div style={s.sideCard}>
            <h3 style={s.sideTitle}><Info size={14} /> DOCUMENTATION</h3>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              <p style={{ marginBottom: '8px' }}>Zones are spatial filters for the AI engine. Only detections within these boundaries will trigger alerts.</p>
              <ul style={{ paddingLeft: '16px', margin: 0 }}>
                <li>Minimum 3 points per zone.</li>
                <li>Multiple zones per camera supported.</li>
                <li>Overlapping zones are permitted.</li>
              </ul>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
