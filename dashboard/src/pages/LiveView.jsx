import { useEffect, useState, useRef, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Maximize2, Minimize2, Monitor, History, ShieldAlert } from 'lucide-react'
import useStore, { API_BASE } from '../store/useStore'
import ZoneOverlay from '../components/ZoneOverlay'

function CameraCard({ camera }) {
  const token = useStore((s) => s.token)
  const streamUrl = `${API_BASE}/api/stream/${camera.cam_id}${token ? `?token=${token}` : ''}`
  const [zones, setZones] = useState([])
  const imgRef = useRef(null)
  const cardRef = useRef(null)
  const [imgSize, setImgSize] = useState({ w: 0, h: 0 })
  const [isHovered, setIsHovered] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)

  useEffect(() => {
    const token = useStore.getState().token
    fetch(`${API_BASE}/api/zones?cam_id=${camera.cam_id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.ok ? r.json() : [])
      .then(setZones)
      .catch(() => {})
  }, [camera.cam_id])

  const handleImgLoad = () => {
    if (imgRef.current) {
      setImgSize({ w: imgRef.current.offsetWidth, h: imgRef.current.offsetHeight })
    }
  }

  const toggleFullscreen = useCallback((e) => {
    e.stopPropagation()
    if (!cardRef.current) return
    if (!document.fullscreenElement) {
      cardRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {})
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {})
    }
  }, [])

  useEffect(() => {
    const onFsChange = () => { if (!document.fullscreenElement) setIsFullscreen(false) }
    document.addEventListener('fullscreenchange', onFsChange)
    return () => document.removeEventListener('fullscreenchange', onFsChange)
  }, [])

  return (
    <div
      ref={cardRef}
      style={{
        ...s.card,
        transform: isHovered && !isFullscreen ? 'translateY(-2px)' : 'translateY(0)',
        borderColor: isHovered ? 'var(--accent-primary)' : 'var(--glass-border)',
        boxShadow: isHovered ? '0 12px 40px rgba(0,0,0,0.6)' : s.card.boxShadow,
        ...(isFullscreen ? { borderRadius: 0, borderWidth: 0, borderStyle: 'none' } : {}),
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div style={{ position: 'relative', background: '#000', flex: 1, overflow: 'hidden' }}>
        <img
          ref={imgRef}
          src={streamUrl}
          alt={`Stream ${camera.cam_id}`}
          style={{ ...s.feed, objectFit: isFullscreen ? 'contain' : 'cover' }}
          onLoad={handleImgLoad}
          onError={(e) => { e.target.src = '' }}
        />
        <ZoneOverlay
          zones={zones}
          camWidth={imgSize.w}
          camHeight={imgSize.h}
          activeZoneIds={new Set()}
        />

        {/* Live dot — always visible, top-right */}
        <div style={s.liveDotWrap}>
          <div style={camera.alive ? s.liveDotGreen : s.liveDotRed} />
        </div>

        {/* Hover overlay: cam name + fullscreen */}
        <div style={{
          ...s.hoverOverlay,
          opacity: isHovered ? 1 : 0,
          pointerEvents: isHovered ? 'auto' : 'none',
        }}>
          <div style={s.hoverCamName}>
            {camera.label || camera.cam_id}
          </div>
          <button style={s.fullscreenBtn} onClick={toggleFullscreen} title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
            {isFullscreen ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}

function WeaponAlarmBanner({ alarm, onDismiss }) {
  const token = useStore((s) => s.token)
  useEffect(() => {
    const timer = setTimeout(onDismiss, 60000)
    return () => clearTimeout(timer)
  }, [alarm, onDismiss])

  return (
    <div style={s.alarmOverlay}>
      <div style={s.alarmBox}>
        <div style={s.alarmHeader}>
          <ShieldAlert size={32} />
          <h1 style={s.alarmTitle}>WEAPON DETECTED</h1>
        </div>
        <p style={s.alarmDetail}>
          LOCATION: <span className="mono">{alarm.cam_id}</span> &bull; THREAT: <span className="mono">{alarm.class_name.toUpperCase()}</span>
          {alarm.confidence != null && ` [CONFIDENCE: ${(alarm.confidence * 100).toFixed(0)}%]`}
        </p>
        {alarm.snapshot_url && (
          <div style={s.alarmSnapshotContainer}>
            <img src={`${API_BASE}${alarm.snapshot_url}${token ? `?token=${token}` : ''}`} alt="Threat Snapshot" style={s.alarmSnapshot} />
          </div>
        )}
        <button style={s.dismissBtn} onClick={onDismiss}>
          ACKNOWLEDGE & DISMISS
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
    const interval = setInterval(fetchCameras, 10000)
    return () => clearInterval(interval)
  }, [])

  const gridCols = gridLayout === '1x1' ? 1 : gridLayout === '3x3' ? 3 : 2

  return (
    <div style={s.root}>
      {weaponAlarm && <WeaponAlarmBanner alarm={weaponAlarm} onDismiss={dismissWeaponAlarm} />}

      <header style={s.header}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <h2 style={s.title}>Surveillance Command</h2>
          <div style={wsConnected ? s.wsStatusOn : s.wsStatusOff}>
            {wsConnected ? 'Network Synchronized' : 'Network Offline'}
          </div>
        </div>
        
        <div style={s.controls}>
          <div style={s.gridSelector}>
            {['1x1', '2x2', '3x3'].map((l) => (
              <button
                key={l}
                style={gridLayout === l ? s.gridBtnActive : s.gridBtn}
                onClick={() => setGridLayout(l)}
              >
                {l}
              </button>
            ))}
          </div>
        </div>
      </header>

      <div style={s.mainLayout}>
        <div
          style={{
            ...s.grid,
            gridTemplateColumns: `repeat(${gridCols}, 1fr)`,
          }}
        >
          {cameras.length === 0 ? (
            <div style={s.emptyState}>
              <Monitor size={48} style={{ opacity: 0.2, marginBottom: '16px' }} />
              <p>NO ACTIVE CAMERA FEEDS</p>
              <Link to="/cameras" style={{...s.addCamPrompt, textDecoration: 'none'}}>CONFIGURE CAMERAS</Link>
            </div>
          ) : (
            cameras.map((cam) => <CameraCard key={cam.cam_id} camera={cam} />)
          )}
        </div>

        <aside style={s.sidebar}>
          <div style={s.sidebarHeader}>
            <History size={16} />
            REAL-TIME INTELLIGENCE
          </div>
          <div style={s.eventList}>
            {events.length === 0 ? (
              <p style={s.sidebarEmpty}>Awaiting detection events...</p>
            ) : (
              events.map((ev, i) => (
                  <div style={s.eventCard}>
                    <div style={s.eventTime}>{ev.timestamp ? new Date(ev.timestamp).toLocaleString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) : '--:--:--'}</div>
                    <div style={s.eventType}>{ev.alert_type?.toUpperCase() || 'UNKNOWN'}</div>
                    <div style={s.eventLocation}>{ev.cam_id}</div>
                  </div>
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  )
}

const s = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    height: 'calc(100vh - 64px)', 
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 0 24px 0',
  },
  title: { margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  wsStatusOn: { fontSize: '0.7rem', color: 'var(--status-success)', background: 'rgba(16, 185, 129, 0.1)', padding: '6px 12px', borderRadius: '20px', fontWeight: 700, letterSpacing: '0.05em' },
  wsStatusOff: { fontSize: '0.7rem', color: 'var(--status-danger)', background: 'rgba(244, 63, 94, 0.1)', padding: '6px 12px', borderRadius: '20px', fontWeight: 700, letterSpacing: '0.05em' },
  
  controls: { display: 'flex', gap: '16px' },
  gridSelector: { background: 'var(--bg-surface)', padding: '6px', borderRadius: 'var(--radius-md)', display: 'flex', gap: '4px', border: '1px solid var(--border-base)', boxShadow: 'var(--shadow-sm)' },
  gridBtn: { background: 'transparent', border: 'none', color: 'var(--text-sub)', padding: '6px 16px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 600, transition: 'all 0.2s' },
  gridBtnActive: { background: 'var(--bg-app)', border: 'none', color: 'var(--text-main)', padding: '6px 16px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, boxShadow: 'var(--shadow-sm)' },

  mainLayout: { display: 'flex', flex: 1, gap: '24px', overflow: 'hidden' },
  grid: {
    display: 'grid',
    flex: 1,
    gap: '24px',
    overflowY: 'auto',
    alignContent: 'start',
    paddingRight: '8px'
  },
  card: {
    background: '#000',
    borderWidth: '1px',
    borderStyle: 'solid',
    borderColor: 'var(--border-base)',
    borderRadius: 'var(--radius-lg)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    position: 'relative',
    transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.2s ease, box-shadow 0.2s ease',
    boxShadow: 'var(--shadow-md)',
  },
  feed: { width: '100%', height: '100%', display: 'block', objectFit: 'cover' },

  // iOS-style live dot — always visible, top-right
  liveDotWrap: {
    position: 'absolute',
    top: '12px',
    right: '12px',
    zIndex: 10,
  },
  liveDotGreen: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    background: '#30d158',
    boxShadow: '0 0 6px 2px rgba(48, 209, 88, 0.6)',
    animation: 'livePulse 2s ease-in-out infinite',
  },
  liveDotRed: {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    background: '#ff453a',
    boxShadow: '0 0 6px 2px rgba(255, 69, 58, 0.5)',
  },

  // Hover overlay — cam name + fullscreen
  hoverOverlay: {
    position: 'absolute',
    inset: 0,
    background: 'linear-gradient(to top, rgba(0,0,0,0.7) 0%, transparent 40%, transparent 60%, rgba(0,0,0,0.4) 100%)',
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    padding: '14px',
    zIndex: 10,
    transition: 'opacity 0.25s ease',
  },
  hoverCamName: {
    color: '#fff',
    fontSize: '0.8rem',
    fontWeight: 700,
    letterSpacing: '0.02em',
    textShadow: '0 1px 4px rgba(0,0,0,0.8)',
  },
  fullscreenBtn: {
    background: 'rgba(255,255,255,0.15)',
    backdropFilter: 'blur(8px)',
    border: '1px solid rgba(255,255,255,0.2)',
    borderRadius: '8px',
    color: '#fff',
    cursor: 'pointer',
    padding: '6px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'background 0.2s',
  },

  sidebar: {
    width: '320px',
    background: 'var(--bg-surface)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-base)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: 'var(--shadow-md)',
  },
  sidebarHeader: {
    padding: '20px',
    fontSize: '0.8rem',
    fontWeight: 800,
    color: 'var(--text-sub)',
    borderBottom: '1px solid var(--border-base)',
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    letterSpacing: '0.05em'
  },
  eventList: { 
    flex: 1, 
    overflowY: 'auto', 
    padding: '16px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px'
  },
  eventCard: {
    padding: '16px',
    background: 'var(--bg-app)',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--border-base)',
    borderLeft: '4px solid var(--accent-primary)',
    transition: 'all 0.2s ease',
    cursor: 'default'
  },
  eventTime: { fontSize: '0.7rem', color: 'var(--text-dim)', marginBottom: '8px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' },
  eventType: { fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '0.02em' },
  eventLocation: { fontSize: '0.75rem', color: 'var(--text-sub)', marginTop: '6px', fontWeight: 500 },
  sidebarEmpty: { textAlign: 'center', padding: '60px 20px', color: 'var(--text-dim)', fontSize: '0.85rem', fontWeight: 500 },

  emptyState: { 
    gridColumn: '1 / -1', 
    height: '400px', 
    display: 'flex', 
    flexDirection: 'column', 
    alignItems: 'center', 
    justifyContent: 'center', 
    color: 'var(--text-dim)',
    fontSize: '0.9rem',
    fontWeight: 600,
    letterSpacing: '1px',
    background: 'var(--bg-surface)',
    borderRadius: 'var(--radius-lg)',
    border: '2px dashed var(--border-bright)'
  },
  addCamPrompt: { marginTop: '24px', background: 'var(--accent-primary)', color: '#fff', border: 'none', padding: '12px 28px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontWeight: 700, boxShadow: '0 4px 12px var(--accent-soft)', display: 'inline-flex', alignItems: 'center' },

  // Alarm Overlay
  alarmOverlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.85)',
    backdropFilter: 'blur(20px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 10000,
    padding: '40px',
    animation: 'fadeIn 0.3s ease-out'
  },
  alarmBox: {
    textAlign: 'center',
    padding: '48px',
    background: '#000',
    border: '2px solid var(--status-danger)',
    borderRadius: 'var(--radius-lg)',
    maxWidth: '700px',
    boxShadow: '0 0 80px rgba(244, 63, 94, 0.4)',
  },
  alarmHeader: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', marginBottom: '32px', color: 'var(--status-danger)' },
  alarmTitle: { fontSize: '3rem', fontWeight: 900, margin: 0, letterSpacing: '-0.02em', lineHeight: 1 },
  alarmDetail: { color: '#ffffff', fontSize: '1.1rem', marginBottom: '32px', fontWeight: 500, letterSpacing: '0.05em' },
  alarmSnapshotContainer: { border: '1px solid rgba(255,255,255,0.2)', borderRadius: 'var(--radius-md)', overflow: 'hidden', marginBottom: '40px', boxShadow: '0 20px 40px rgba(0,0,0,0.5)' },
  alarmSnapshot: { width: '100%', display: 'block' },
  dismissBtn: {
    background: 'var(--status-danger)',
    color: '#fff',
    border: 'none',
    padding: '18px 48px',
    borderRadius: 'var(--radius-md)',
    fontSize: '1rem',
    fontWeight: 800,
    cursor: 'pointer',
    letterSpacing: '0.05em',
    transition: 'transform 0.1s active',
    boxShadow: '0 8px 24px rgba(244, 63, 94, 0.4)'
  },
}
