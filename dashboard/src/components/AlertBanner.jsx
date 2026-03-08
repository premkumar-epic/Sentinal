import { useEffect } from 'react'
import useStore from '../store/useStore'

export default function AlertBanner() {
  const weaponAlarm = useStore(s => s.weaponAlarm)
  const dismissWeaponAlarm = useStore(s => s.dismissWeaponAlarm)

  useEffect(() => {
    if (!weaponAlarm) return

    // Play audio beep
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)()
      const osc = ctx.createOscillator()
      osc.connect(ctx.destination)
      osc.frequency.setValueAtTime(880, ctx.currentTime)
      osc.start()
      osc.stop(ctx.currentTime + 0.3)
    } catch (_) {}

    // Auto-dismiss after 60 seconds
    const timer = setTimeout(() => {
      dismissWeaponAlarm()
    }, 60000)

    return () => clearTimeout(timer)
  }, [weaponAlarm, dismissWeaponAlarm])

  if (!weaponAlarm) return null

  return (
    <div style={s.overlay}>
      <div style={s.content}>
        <div style={s.header}>
          <h1 style={s.title}>⚠️ WEAPON DETECTED</h1>
          <p style={s.subtitle}>
            Camera: <strong>{weaponAlarm.cam_id}</strong> — Class: <strong>{weaponAlarm.class_name}</strong>
          </p>
        </div>

        {weaponAlarm.snapshot_url && (
          <img
            src={weaponAlarm.snapshot_url}
            alt="weapon snapshot"
            style={s.snapshot}
          />
        )}

        <button style={s.dismissBtn} onClick={dismissWeaponAlarm}>
          DISMISS
        </button>
      </div>
    </div>
  )
}

const s = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: '#CC0000',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 9999,
    animation: 'weaponFlash 0.5s infinite alternate',
  },
  content: {
    textAlign: 'center',
    color: '#fff',
    fontFamily: 'monospace',
  },
  header: {
    marginBottom: '20px',
  },
  title: {
    fontSize: '3rem',
    margin: '0 0 10px',
    fontWeight: 'bold',
    textShadow: '0 2px 10px rgba(0,0,0,0.5)',
  },
  subtitle: {
    fontSize: '1.2rem',
    margin: 0,
  },
  snapshot: {
    maxWidth: '600px',
    maxHeight: '400px',
    objectFit: 'contain',
    borderRadius: '8px',
    border: '3px solid #fff',
    marginBottom: '20px',
  },
  dismissBtn: {
    padding: '12px 40px',
    fontSize: '1.1rem',
    fontWeight: 'bold',
    background: '#fff',
    color: '#CC0000',
    border: 'none',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'transform 0.2s',
  },
}

// Add CSS animation
const style = document.createElement('style')
style.textContent = `
  @keyframes weaponFlash {
    from { opacity: 1; }
    to { opacity: 0.5; }
  }
`
if (typeof document !== 'undefined') {
  document.head.appendChild(style)
}
