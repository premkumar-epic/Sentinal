import React, { useEffect } from 'react'
import { ShieldAlert, X, AlertTriangle, Eye } from 'lucide-react'
import useStore, { API_BASE } from '../store/useStore'

export default function AlertBanner() {
  const alarm = useStore((s) => s.weaponAlarm)
  const dismiss = useStore((s) => s.dismissWeaponAlarm)

  useEffect(() => {
    if (alarm) {
      // Play system alert sound if available
      const audio = new Audio('/alert.mp3')
      audio.play().catch(() => {}) // Handle browsers blocking autoplay
      
      const timer = setTimeout(dismiss, 60000)
      return () => clearTimeout(timer)
    }
  }, [alarm, dismiss])

  if (!alarm) return null

  return (
    <div style={s.overlay}>
      <div style={s.modal}>
        <div style={s.header}>
          <div style={s.iconBox}>
            <ShieldAlert size={32} color="var(--status-danger)" />
          </div>
          <div style={s.titleGroup}>
            <h1 style={s.title}>WEAPON DETECTED</h1>
            <p style={s.subtitle}>CRITICAL SECURITY PROTOCOL INITIALIZED</p>
          </div>
          <button style={s.closeBtn} onClick={dismiss}>
            <X size={24} />
          </button>
        </div>

        <div style={s.body}>
          <div style={s.evidence}>
            {alarm.snapshot_url ? (
              <img
                src={`${API_BASE}${alarm.snapshot_url}${alarm.snapshot_url.includes('?') ? '&' : '?'}token=${useStore.getState().token || ''}`}
                alt="FORENSIC EVIDENCE"
                style={s.snapshot}
              />
            ) : (
              <div style={s.noSnapshot}>
                <AlertTriangle size={48} opacity={0.2} />
                <p>AWAITING FORENSIC DATA</p>
              </div>
            )}
          </div>

          <div style={s.meta}>
            <div style={s.field}>
              <label style={s.label}>ORIGIN NODE</label>
              <div style={s.value} className="mono">{alarm.cam_id}</div>
            </div>
            <div style={s.field}>
              <label style={s.label}>THREAT CLASSIFICATION</label>
              <div style={{ ...s.value, color: 'var(--status-danger)' }}>{alarm.class_name?.toUpperCase() || 'UNKNOWN'}</div>
            </div>
            <div style={s.field}>
              <label style={s.label}>CONFIDENCE SCORE</label>
              <div style={s.confidenceContainer}>
                <div style={s.confidenceLabel}>{(alarm.confidence * 100).toFixed(1)}%</div>
                <div style={s.barBg}>
                  <div style={{ ...s.barFill, width: `${(alarm.confidence || 0) * 100}%` }} />
                </div>
              </div>
            </div>
            
            <button style={s.ackBtn} onClick={dismiss}>
              ACKNOWLEDGE THREAT
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

const s = {
  overlay: {
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
  modal: {
    background: '#000',
    border: '2px solid var(--status-danger)',
    borderRadius: 'var(--radius-lg)',
    maxWidth: '900px',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    boxShadow: '0 0 80px rgba(244, 63, 94, 0.3)'
  },
  header: {
    padding: '24px 32px',
    borderBottom: '1px solid rgba(244, 63, 94, 0.2)',
    display: 'flex',
    alignItems: 'center',
    gap: '24px'
  },
  iconBox: {
    width: '64px',
    height: '64px',
    background: 'rgba(244, 63, 94, 0.1)',
    borderRadius: 'var(--radius-md)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid rgba(244, 63, 94, 0.3)'
  },
  titleGroup: { flex: 1 },
  title: { 
    margin: 0, 
    fontSize: '2rem', 
    fontWeight: 900, 
    color: 'var(--status-danger)', 
    letterSpacing: '-1px',
    lineHeight: '1'
  },
  subtitle: { 
    margin: '4px 0 0', 
    fontSize: '0.75rem', 
    fontWeight: 800, 
    color: 'var(--text-dim)', 
    letterSpacing: '2px' 
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: 'var(--text-dim)',
    cursor: 'pointer',
    padding: '8px'
  },
  body: {
    display: 'grid',
    gridTemplateColumns: '1.2fr 1fr',
    flex: 1
  },
  evidence: {
    background: '#000',
    padding: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center'
  },
  snapshot: {
    maxWidth: '100%',
    maxHeight: '400px',
    borderRadius: 'var(--radius-md)',
    border: '1px solid var(--glass-border)',
    boxShadow: '0 20px 40px rgba(0,0,0,0.5)'
  },
  noSnapshot: {
    color: 'var(--text-dim)',
    textAlign: 'center',
    fontSize: '0.75rem',
    letterSpacing: '1px'
  },
  meta: {
    padding: '32px',
    borderLeft: '1px solid rgba(255,255,255,0.05)',
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    justifyContent: 'center'
  },
  field: { display: 'flex', flexDirection: 'column', gap: '8px' },
  label: { 
    fontSize: '0.65rem', 
    fontWeight: 800, 
    color: 'var(--text-dim)', 
    letterSpacing: '1px' 
  },
  value: { 
    fontSize: '1.1rem', 
    fontWeight: 800, 
    color: 'var(--text-primary)' 
  },
  confidenceContainer: { display: 'flex', alignItems: 'center', gap: '12px' },
  confidenceLabel: { fontSize: '0.9rem', fontWeight: 900, color: 'var(--text-primary)', width: '50px' },
  barBg: { flex: 1, height: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: '4px', overflow: 'hidden' },
  barFill: { height: '100%', background: 'var(--status-danger)', borderRadius: '4px' },
  ackBtn: {
    marginTop: '12px',
    background: 'var(--status-danger)',
    color: '#fff',
    border: 'none',
    padding: '16px',
    borderRadius: 'var(--radius-md)',
    fontSize: '0.9rem',
    fontWeight: 900,
    cursor: 'pointer',
    letterSpacing: '1px',
    transition: 'transform 0.1s active'
  }
}
