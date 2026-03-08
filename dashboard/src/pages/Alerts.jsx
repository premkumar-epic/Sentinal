import { useState, useEffect } from 'react'
import { API_BASE } from '../store/useStore'

export default function Alerts() {
  const [config, setConfig] = useState({
    alert_email_enabled: false,
    alert_email_smtp_host: '',
    alert_email_smtp_port: 587,
    alert_email_sender: '',
    alert_email_recipient: '',
    alert_email_password: '',
    alert_webhook_enabled: false,
    alert_webhook_url: '',
  })

  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  // Load config on mount
  useEffect(() => {
    fetchConfig()
  }, [])

  const fetchConfig = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/alerts/config`)
      if (res.ok) {
        setConfig(await res.json())
      }
    } catch (err) {
      console.error('Failed to fetch alert config:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target
    setConfig({
      ...config,
      [name]: type === 'checkbox' ? checked : type === 'number' ? parseInt(value) : value,
    })
  }

  const handleSave = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/alerts/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      })
      if (res.ok) {
        setStatus('✓ Config saved successfully')
        setTimeout(() => setStatus(''), 3000)
      } else {
        setStatus('✗ Failed to save config')
      }
    } catch (err) {
      console.error('Failed to save config:', err)
      setStatus('✗ Error saving config')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (channel) => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/alerts/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel }),
      })
      if (res.ok) {
        const result = await res.json()
        if (channel === 'email') {
          setStatus(`✓ Test email sent to ${result.email}`)
        } else if (channel === 'webhook') {
          setStatus(`✓ Webhook test sent to ${result.webhook}`)
        }
      } else {
        setStatus(`✗ Test failed for ${channel}`)
      }
      setTimeout(() => setStatus(''), 4000)
    } catch (err) {
      console.error(`Failed to test ${channel}:`, err)
      setStatus(`✗ Error testing ${channel}`)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !config.alert_email_enabled) {
    return <div style={s.root}><p style={s.dim}>Loading...</p></div>
  }

  return (
    <div style={s.root}>
      <h2 style={s.title}>Alert Configuration</h2>

      {status && (
        <div
          style={{
            ...s.status,
            background: status.startsWith('✓') ? '#1a3a1a' : '#3a1a1a',
            color: status.startsWith('✓') ? '#00ff00' : '#ff6666',
          }}
        >
          {status}
        </div>
      )}

      <form onSubmit={handleSave} style={s.form}>
        {/* Email Section */}
        <fieldset style={s.fieldset}>
          <legend style={s.legend}>Email Alerts</legend>

          <div style={s.formRow}>
            <label style={s.label}>
              <input
                type="checkbox"
                name="alert_email_enabled"
                checked={config.alert_email_enabled}
                onChange={handleInputChange}
                style={s.checkbox}
              />
              Enable email alerts
            </label>
          </div>

          {config.alert_email_enabled && (
            <>
              <div style={s.formRow}>
                <label style={s.label}>SMTP Host</label>
                <input
                  type="text"
                  name="alert_email_smtp_host"
                  value={config.alert_email_smtp_host}
                  onChange={handleInputChange}
                  placeholder="smtp.gmail.com"
                  style={s.input}
                />
              </div>

              <div style={s.formRow}>
                <label style={s.label}>SMTP Port</label>
                <input
                  type="number"
                  name="alert_email_smtp_port"
                  value={config.alert_email_smtp_port}
                  onChange={handleInputChange}
                  placeholder="587"
                  style={s.input}
                />
              </div>

              <div style={s.formRow}>
                <label style={s.label}>Sender Email</label>
                <input
                  type="email"
                  name="alert_email_sender"
                  value={config.alert_email_sender}
                  onChange={handleInputChange}
                  placeholder="your-email@gmail.com"
                  style={s.input}
                />
              </div>

              <div style={s.formRow}>
                <label style={s.label}>Recipient Email</label>
                <input
                  type="email"
                  name="alert_email_recipient"
                  value={config.alert_email_recipient}
                  onChange={handleInputChange}
                  placeholder="alert@example.com"
                  style={s.input}
                />
              </div>

              <div style={s.formRow}>
                <label style={s.label}>Password</label>
                <input
                  type="password"
                  name="alert_email_password"
                  value={config.alert_email_password}
                  onChange={handleInputChange}
                  placeholder="••••••••"
                  style={s.input}
                />
              </div>

              <button
                type="button"
                style={s.testBtn}
                onClick={() => handleTest('email')}
              >
                Test Email
              </button>
            </>
          )}
        </fieldset>

        {/* Webhook Section */}
        <fieldset style={s.fieldset}>
          <legend style={s.legend}>Webhook Alerts</legend>

          <div style={s.formRow}>
            <label style={s.label}>
              <input
                type="checkbox"
                name="alert_webhook_enabled"
                checked={config.alert_webhook_enabled}
                onChange={handleInputChange}
                style={s.checkbox}
              />
              Enable webhook alerts
            </label>
          </div>

          {config.alert_webhook_enabled && (
            <>
              <div style={s.formRow}>
                <label style={s.label}>Webhook URL</label>
                <input
                  type="url"
                  name="alert_webhook_url"
                  value={config.alert_webhook_url}
                  onChange={handleInputChange}
                  placeholder="https://example.com/webhook"
                  style={s.input}
                />
              </div>

              <button
                type="button"
                style={s.testBtn}
                onClick={() => handleTest('webhook')}
              >
                Test Webhook
              </button>
            </>
          )}
        </fieldset>

        {/* Save Button */}
        <div style={s.actions}>
          <button type="submit" style={s.btn}>
            Save Configuration
          </button>
        </div>
      </form>
    </div>
  )
}

const s = {
  root: {
    padding: '16px',
    background: '#0d0d0d',
    minHeight: '100vh',
    color: '#e0e0e0',
    fontFamily: 'monospace',
  },
  title: {
    margin: '0 0 20px',
    color: '#00e5ff',
    fontSize: '1.3rem',
  },
  status: {
    padding: '12px 16px',
    borderRadius: '4px',
    marginBottom: '16px',
    fontSize: '0.9rem',
    border: '1px solid rgba(255,255,255,0.2)',
  },
  form: {
    maxWidth: '600px',
  },
  fieldset: {
    border: '1px solid #333',
    borderRadius: '6px',
    padding: '16px',
    marginBottom: '20px',
    background: '#1a1a1a',
  },
  legend: {
    color: '#00e5ff',
    fontSize: '1rem',
    fontWeight: 'bold',
    padding: '0 8px',
  },
  formRow: {
    marginBottom: '12px',
  },
  label: {
    display: 'block',
    color: '#aaa',
    fontSize: '0.85rem',
    marginBottom: '4px',
  },
  checkbox: {
    marginRight: '6px',
  },
  input: {
    width: '100%',
    padding: '8px',
    background: '#0d0d0d',
    border: '1px solid #444',
    borderRadius: '3px',
    color: '#e0e0e0',
    fontSize: '0.85rem',
    boxSizing: 'border-box',
  },
  btn: {
    padding: '8px 20px',
    background: '#00e5ff',
    color: '#000',
    border: 'none',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.85rem',
    fontWeight: 'bold',
  },
  testBtn: {
    padding: '6px 12px',
    background: '#666',
    color: '#fff',
    border: 'none',
    borderRadius: '3px',
    cursor: 'pointer',
    fontSize: '0.8rem',
    marginTop: '8px',
  },
  actions: {
    display: 'flex',
    gap: '12px',
  },
  dim: {
    color: '#555',
  },
}
