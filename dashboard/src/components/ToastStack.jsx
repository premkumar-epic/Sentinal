import { X, AlertTriangle, ShieldAlert, Eye, Users } from 'lucide-react'
import useStore from '../store/useStore'

const severityConfig = {
  danger: {
    border: 'var(--status-danger)',
    bg: 'rgba(244, 63, 94, 0.08)',
    icon: ShieldAlert,
    accent: 'var(--status-danger)',
  },
  warning: {
    border: 'var(--status-warning, #f59e0b)',
    bg: 'rgba(245, 158, 11, 0.08)',
    icon: AlertTriangle,
    accent: 'var(--status-warning, #f59e0b)',
  },
  info: {
    border: 'var(--accent-primary)',
    bg: 'rgba(99, 102, 241, 0.08)',
    icon: Eye,
    accent: 'var(--accent-primary)',
  },
}

function Toast({ toast, onDismiss }) {
  const cfg = severityConfig[toast.severity] || severityConfig.warning
  const Icon = cfg.icon

  const time = toast.timestamp
    ? new Date(toast.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    : null

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border-base)',
      borderLeft: `4px solid ${cfg.border}`,
      borderRadius: 'var(--radius-md)',
      padding: '14px 16px',
      display: 'flex',
      alignItems: 'flex-start',
      gap: '12px',
      boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
      animation: 'toastSlideIn 0.3s ease-out',
      maxWidth: '400px',
      width: '100%',
    }}>
      <div style={{
        width: '32px',
        height: '32px',
        borderRadius: 'var(--radius-sm)',
        background: cfg.bg,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}>
        <Icon size={16} color={cfg.accent} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: '0.8rem',
          fontWeight: 800,
          color: cfg.accent,
          letterSpacing: '0.04em',
          marginBottom: '4px',
        }}>
          {toast.title}
        </div>
        <div style={{
          fontSize: '0.78rem',
          color: 'var(--text-sub)',
          fontWeight: 500,
          lineHeight: 1.4,
        }}>
          {toast.message}
        </div>
        {time && (
          <div style={{
            fontSize: '0.65rem',
            color: 'var(--text-dim)',
            marginTop: '6px',
            fontWeight: 700,
            letterSpacing: '0.03em',
          }}>
            {time}
          </div>
        )}
      </div>

      <button
        onClick={() => onDismiss(toast.id)}
        style={{
          background: 'transparent',
          border: 'none',
          color: 'var(--text-dim)',
          cursor: 'pointer',
          padding: '4px',
          flexShrink: 0,
        }}
      >
        <X size={14} />
      </button>
    </div>
  )
}

export default function ToastStack() {
  const toasts = useStore((s) => s.toasts)
  const dismissToast = useStore((s) => s.dismissToast)

  if (toasts.length === 0) return null

  return (
    <div style={{
      position: 'fixed',
      top: '24px',
      right: '24px',
      zIndex: 9000,
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      pointerEvents: 'none',
    }}>
      {toasts.map((t) => (
        <div key={t.id} style={{ pointerEvents: 'auto' }}>
          <Toast toast={t} onDismiss={dismissToast} />
        </div>
      ))}
    </div>
  )
}
