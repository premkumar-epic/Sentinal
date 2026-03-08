import { useEffect, useState, useRef } from 'react'
import useStore, { API_BASE } from '../store/useStore'
import ZoneOverlay from '../components/ZoneOverlay'

function CameraCard({ camera }) {
  const streamUrl = `${API_BASE}/api/stream/${camera.cam_id}`
  const [zones, setZones] = useState([])
  const imgRef = useRef(null)
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 })

  useEffect(() => {
    fetch(`${API_BASE}/api/zones?cam_id=${camera.cam_id}`)
      .then((r) => r.ok ? r.json() : [])
      .then(setZones)
      .catch(() => {})
  }, [camera.cam_id])

  const handleImgLoad = () => {
    if (imgRef.current) {
      setImgSize({ w: imgRef.current.offsetWidth, h: imgRef.current.offsetHeight })
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <span style={styles.label}>{camera.label || camera.cam_id}</span>
        <span style={camera.alive ? styles.dotGreen : styles.dotRed} />
      </div>
      <div style={{ position: 'relative' }}>
        <img
          ref={imgRef}
          src={streamUrl}
          alt={`Stream ${camera.cam_id}`}
          style={styles.feed}
          onLoad={handleImgLoad}
        />
        <ZoneOverlay
          zones={zones}
          camWidth={imgSize.w}
          camHeight={imgSize.h}
          activeZoneIds={new Set()}
        />
      </div>
    </div>
  )
}

function WeaponAlarmBanner({ alarm, onDismiss }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, 60000)
    return () => clearTimeout(timer)
  }, [alarm, onDismiss])

  return (
    <div style={styles.alarmOverlay}>
      <div style={styles.alarmBox}>
        <h1 style={styles.alarmTitle}>⚠ WEAPON DETECTED</h1>
        <p style={styles.alarmDetail}>
          Camera: {alarm.cam_id} — {alarm.class_name}
          {alarm.confidence != null && ` (${(alarm.confidence * 100).toFixed(0)}%)`}
        </p>
        {alarm.snapshot_url && (
          <img src={`${API_BASE}${alarm.snapshot_url}`} alt="Snapshot" style={styles.alarmSnapshot} />
        )}
        <button style={styles.dismissBtn} onClick={onDismiss}>
          DISMISS
        </button>
      </div>
    </div>
  )
}

export default function LiveView() {
  const cameras = useStore((s) => s.cameras)
  const events = useStore((s) => s.events)
  const weaponAlarm = useStore((s) => s.weaponAlarm)
  const wsConnected = useStore((s) => s.wsConnected)
  const gridLayout = useStore((s) => s.gridLayout)
  const fetchCameras = useStore((s) => s.fetchCameras)
  const startWebSocket = useStore((s) => s.startWebSocket)
  const stopWebSocket = useStore((s) => s.stopWebSocket)
  const dismissWeaponAlarm = useStore((s) => s.dismissWeaponAlarm)
  const setGridLayout = useStore((s) => s.setGridLayout)

  useEffect(() => {
    fetchCameras()
    startWebSocket()
    const interval = setInterval(fetchCameras, 10000)
    return () => {
      clearInterval(interval)
      stopWebSocket()
    }
  }, [])

  const gridCols = gridLayout === '1x1' ? 1 : gridLayout === '3x3' ? 3 : 2

  return (
    <div style={styles.root}>
      {weaponAlarm && <WeaponAlarmBanner alarm={weaponAlarm} onDismiss={dismissWeaponAlarm} />}

      <div style={styles.topBar}>
        <h2 style={styles.title}>SENTINAL — Live View</h2>
        <div style={styles.controls}>
          {['1x1', '2x2', '3x3'].map((l) => (
            <button
              key={l}
              style={gridLayout === l ? styles.btnActive : styles.btn}
              onClick={() => setGridLayout(l)}
            >
              {l}
            </button>
          ))}
          <span style={wsConnected ? styles.wsGreen : styles.wsRed}>
            {wsConnected ? '● WS' : '○ WS'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <div
          style={{
            ...styles.grid,
            gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
          }}
        >
          {cameras.length === 0 ? (
            <div style={styles.empty}>No cameras added yet.</div>
          ) : (
            cameras.map((cam) => <CameraCard key={cam.cam_id} camera={cam} />)
          )}
        </div>

        <div style={styles.sidebar}>
          <h3 style={styles.sidebarTitle}>Event Feed</h3>
          {events.length === 0 ? (
            <p style={styles.sidebarEmpty}>No events yet.</p>
          ) : (
            events.map((ev, i) => (
              <div key={i} style={styles.eventItem}>
                <span style={styles.eventType}>{ev.alert_type || ev.type}</span>
                <span style={styles.eventMeta}>
                  {ev.cam_id} · {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : ''}
                </span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Inline styles — no external CSS dependency for Phase 1 milestone
// ---------------------------------------------------------------------------
const styles = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    background: '#0d0d0d',
    color: '#e0e0e0',
    fontFamily: 'monospace',
  },
  topBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '8px 16px',
    background: '#1a1a1a',
    borderBottom: '1px solid #333',
  },
  title: { margin: 0, fontSize: '1rem', color: '#00e5ff' },
  controls: { display: 'flex', alignItems: 'center', gap: '8px' },
  btn: {
    padding: '2px 8px',
    background: '#2a2a2a',
    color: '#aaa',
    border: '1px solid #444',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  btnActive: {
    padding: '2px 8px',
    background: '#00e5ff',
    color: '#000',
    border: '1px solid #00e5ff',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.75rem',
  },
  wsGreen: { color: '#00e676', fontSize: '0.75rem' },
  wsRed: { color: '#ff1744', fontSize: '0.75rem' },
  grid: {
    display: 'grid',
    flex: 1,
    gap: '8px',
    padding: '8px',
    overflowY: 'auto',
    alignContent: 'start',
    height: '100%',
  },
  card: {
    background: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '4px',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 'calc(100vh - 100px)',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '4px 8px',
    background: '#111',
  },
  label: { fontSize: '0.75rem', color: '#aaa' },
  dotGreen: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: '#00e676',
    display: 'inline-block',
  },
  dotRed: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    background: '#ff1744',
    display: 'inline-block',
  },
  feed: { width: '100%', display: 'block', objectFit: 'contain' },
  empty: { color: '#555', padding: '32px', gridColumn: '1 / -1', textAlign: 'center' },
  sidebar: {
    width: '240px',
    minWidth: '240px',
    background: '#111',
    borderLeft: '1px solid #333',
    padding: '8px',
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  sidebarTitle: { margin: '0 0 8px', fontSize: '0.85rem', color: '#00e5ff' },
  sidebarEmpty: { color: '#555', fontSize: '0.75rem' },
  eventItem: {
    padding: '4px 6px',
    background: '#1a1a1a',
    borderRadius: '3px',
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    borderLeft: '3px solid #00e5ff',
  },
  eventType: { fontSize: '0.75rem', fontWeight: 'bold', color: '#ff9100' },
  eventMeta: { fontSize: '0.65rem', color: '#777' },
  // Weapon alarm overlay
  alarmOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(180,0,0,0.92)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    animation: 'none',
  },
  alarmBox: {
    textAlign: 'center',
    padding: '40px',
    background: '#1a0000',
    border: '3px solid #ff1744',
    borderRadius: '8px',
    maxWidth: '600px',
  },
  alarmTitle: { color: '#ff1744', fontSize: '2rem', margin: '0 0 16px' },
  alarmDetail: { color: '#fff', fontSize: '1.1rem', margin: '0 0 16px' },
  alarmSnapshot: { maxWidth: '100%', maxHeight: '300px', margin: '0 0 16px', borderRadius: '4px' },
  dismissBtn: {
    padding: '10px 32px',
    background: '#ff1744',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    fontSize: '1rem',
    cursor: 'pointer',
    fontWeight: 'bold',
  },
}
