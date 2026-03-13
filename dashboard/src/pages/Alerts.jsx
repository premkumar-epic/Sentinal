import { useState, useEffect, useCallback } from 'react'
import { Bell, Mail, Webhook, Save, Send, ShieldCheck, ShieldAlert, CheckCircle2, AlertTriangle, Settings, MessageCircle } from 'lucide-react'
import useStore from '../store/useStore'

export default function Alerts() {
  const fetchAlertConfigStore = useStore((s) => s.fetchAlertConfig)
  const updateAlertConfigStore = useStore((s) => s.updateAlertConfig)
  const testAlertStore = useStore((s) => s.testAlert)

  const [config, setConfig] = useState({
    email_enabled: false,
    email_smtp_host: '',
    email_smtp_port: 587,
    email_sender: '',
    email_recipient: '',
    email_password: '',
    webhook_enabled: false,
    webhook_url: '',
    telegram_enabled: false,
    telegram_bot_token: '',
    telegram_chat_id: '',
  })

  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(false)

  const fetchConfig = useCallback(async () => {
    setLoading(true)
    try {
      const data = await fetchAlertConfigStore()
      if (data) {
        setConfig(data)
      }
    } catch (err) {
      console.error('Config synchronization failure:', err)
    } finally {
      setLoading(false)
    }
  }, [fetchAlertConfigStore])

  useEffect(() => {
    fetchConfig()
  }, [fetchConfig])

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
      const success = await updateAlertConfigStore(config)
      if (success) {
        setStatus('PROTOCOL UPDATED: CONFIGURATION PERSISTED')
        setTimeout(() => setStatus(''), 3000)
      } else {
        setStatus('FAULT: UPDATE REJECTED BY SERVER')
      }
    } catch (err) {
      console.error('Save failure:', err)
      setStatus('CRITICAL FAULT: IO ERROR')
    } finally {
      setLoading(false)
    }
  }

  const handleTest = async (channel) => {
    setLoading(true)
    try {
      const success = await testAlertStore(channel)
      if (success) {
        setStatus(`DIAGNOSTIC COMPLETE: ${channel.toUpperCase()} DISPATCHED`)
      } else {
        setStatus(`DIAGNOSTIC FAILURE: ${channel.toUpperCase()} FAULT`)
      }
      setTimeout(() => setStatus(''), 4000)
    } catch (err) {
      console.error(`Diagnostic failure for ${channel}:`, err)
      setStatus(`CRITICAL FAULT: ${channel.toUpperCase()} UNREACHABLE`)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !config.email_smtp_host) {
    return (
      <div style={s.root}>
        <div style={s.loadingBox}>
          <Settings size={32} style={s.spin} />
          <p>INITIALIZING CONFIGURATION INTERFACE...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>Dispatch Protocols</h2>
          <p style={s.subtitle}>Configure automated threat notification and external integrations</p>
        </div>
      </header>

      {status && (
        <div style={{
          ...s.statusBanner,
          backgroundColor: status.includes('FAULT') ? 'rgba(244, 63, 94, 0.1)' : 'rgba(16, 185, 129, 0.1)',
          borderColor: status.includes('FAULT') ? 'var(--status-danger)' : 'var(--status-success)',
          color: status.includes('FAULT') ? 'var(--status-danger)' : 'var(--status-success)',
        }}>
          {status.includes('FAULT') ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
          {status}
        </div>
      )}

      <form onSubmit={handleSave} style={s.formLayout}>
        <div style={s.mainContent}>
          {/* Email Channel */}
          <section style={{ ...s.module, borderColor: config.email_enabled ? 'var(--status-success)' : 'var(--glass-border)' }}>
            <div style={s.moduleHeader}>
              <div style={s.moduleIcon}><Mail size={20} color={config.email_enabled ? 'var(--status-success)' : 'var(--text-dim)'} /></div>
              <div style={{ flex: 1 }}>
                <h3 style={s.moduleTitle}>SMTP DISPATCH</h3>
                <p style={s.moduleDesc}>Automated email reports with threat snapshots</p>
              </div>
              <label style={s.switch}>
                <input
                  type="checkbox"
                  name="email_enabled"
                  checked={config.email_enabled}
                  onChange={handleInputChange}
                  style={{ display: 'none' }}
                />
                <div style={{ ...s.switchKnob, background: config.email_enabled ? 'var(--status-success)' : 'var(--text-dim)' }}>
                  {config.email_enabled ? 'ACTIVE' : 'OFF'}
                </div>
              </label>
            </div>

            <div style={{ ...s.moduleBody, opacity: config.email_enabled ? 1 : 0.4, pointerEvents: config.email_enabled ? 'auto' : 'none' }}>
              <div style={s.fieldGrid}>
                <div style={s.inputGroup}>
                  <label style={s.label}>SMTP SERVER</label>
                  <input
                    type="text"
                    name="email_smtp_host"
                    value={config.email_smtp_host}
                    onChange={handleInputChange}
                    placeholder="smtp.provider.com"
                    style={s.input}
                  />
                </div>
                <div style={s.inputGroup}>
                  <label style={s.label}>PORT</label>
                  <input
                    type="number"
                    name="email_smtp_port"
                    value={config.email_smtp_port}
                    onChange={handleInputChange}
                    placeholder="587"
                    style={s.input}
                  />
                </div>
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>ORIGIN ADDRESS</label>
                <input
                  type="email"
                  name="email_sender"
                  value={config.email_sender}
                  onChange={handleInputChange}
                  placeholder="sentinal-core@system.internal"
                  style={s.input}
                />
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>TARGET RECIPIENT</label>
                <input
                  type="email"
                  name="email_recipient"
                  value={config.email_recipient}
                  onChange={handleInputChange}
                  placeholder="security-head@org.com"
                  style={s.input}
                />
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>AUTHORIZATION TOKEN / PASSWORD</label>
                <input
                  type="password"
                  name="email_password"
                  value={config.email_password}
                  onChange={handleInputChange}
                  placeholder="••••••••••••••••"
                  style={s.input}
                />
              </div>

              <button
                type="button"
                style={s.testBtn}
                onClick={() => handleTest('email')}
                disabled={!config.email_enabled}
              >
                <Send size={14} /> RUN SMTP DIAGNOSTIC
              </button>
            </div>
          </section>

          {/* Webhook Channel */}
          <section style={{ ...s.module, borderColor: config.webhook_enabled ? 'var(--status-success)' : 'var(--glass-border)' }}>
            <div style={s.moduleHeader}>
              <div style={s.moduleIcon}><Webhook size={20} color={config.webhook_enabled ? 'var(--status-success)' : 'var(--text-dim)'} /></div>
              <div style={{ flex: 1 }}>
                <h3 style={s.moduleTitle}>WEBHOOK INTEGRATION</h3>
                <p style={s.moduleDesc}>Real-time JSON payloads for external security systems</p>
              </div>
              <label style={s.switch}>
                <input
                  type="checkbox"
                  name="webhook_enabled"
                  checked={config.webhook_enabled}
                  onChange={handleInputChange}
                  style={{ display: 'none' }}
                />
                <div style={{ ...s.switchKnob, background: config.webhook_enabled ? 'var(--status-success)' : 'var(--text-dim)' }}>
                  {config.webhook_enabled ? 'ACTIVE' : 'OFF'}
                </div>
              </label>
            </div>

            <div style={{ ...s.moduleBody, opacity: config.webhook_enabled ? 1 : 0.4, pointerEvents: config.webhook_enabled ? 'auto' : 'none' }}>
              <div style={s.inputGroup}>
                <label style={s.label}>ENDPOINT URL</label>
                <input
                  type="url"
                  name="webhook_url"
                  value={config.webhook_url}
                  onChange={handleInputChange}
                  placeholder="https://api.security-corp.com/v1/alerts"
                  style={s.input}
                />
              </div>

              <button
                type="button"
                style={s.testBtn}
                onClick={() => handleTest('webhook')}
                disabled={!config.webhook_enabled}
              >
                <Send size={14} /> RUN WEBHOOK DIAGNOSTIC
              </button>
            </div>
          </section>

          {/* Telegram Channel */}
          <section style={{ ...s.module, borderColor: config.telegram_enabled ? 'var(--status-success)' : 'var(--glass-border)' }}>
            <div style={s.moduleHeader}>
              <div style={s.moduleIcon}><MessageCircle size={20} color={config.telegram_enabled ? 'var(--status-success)' : 'var(--text-dim)'} /></div>
              <div style={{ flex: 1 }}>
                <h3 style={s.moduleTitle}>TELEGRAM BOT</h3>
                <p style={s.moduleDesc}>Instant mobile alerts with threat snapshots via Telegram</p>
              </div>
              <label style={s.switch}>
                <input
                  type="checkbox"
                  name="telegram_enabled"
                  checked={config.telegram_enabled}
                  onChange={handleInputChange}
                  style={{ display: 'none' }}
                />
                <div style={{ ...s.switchKnob, background: config.telegram_enabled ? 'var(--status-success)' : 'var(--text-dim)' }}>
                  {config.telegram_enabled ? 'ACTIVE' : 'OFF'}
                </div>
              </label>
            </div>

            <div style={{ ...s.moduleBody, opacity: config.telegram_enabled ? 1 : 0.4, pointerEvents: config.telegram_enabled ? 'auto' : 'none' }}>
              <div style={s.inputGroup}>
                <label style={s.label}>BOT TOKEN</label>
                <input
                  type="password"
                  name="telegram_bot_token"
                  value={config.telegram_bot_token}
                  onChange={handleInputChange}
                  placeholder="123456789:ABCdefGHIjklMNOpqrSTUvwxYZ"
                  style={s.input}
                />
                <span style={s.hint}>Get from @BotFather on Telegram</span>
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>CHAT ID</label>
                <input
                  type="text"
                  name="telegram_chat_id"
                  value={config.telegram_chat_id}
                  onChange={handleInputChange}
                  placeholder="-1001234567890"
                  style={s.input}
                />
                <span style={s.hint}>User, group, or channel ID — get from @userinfobot</span>
              </div>

              <button
                type="button"
                style={s.testBtn}
                onClick={() => handleTest('telegram')}
                disabled={!config.telegram_enabled}
              >
                <Send size={14} /> RUN TELEGRAM DIAGNOSTIC
              </button>
            </div>
          </section>
        </div>

        {/* Action Sidebar */}
        <aside style={s.sidebar}>
          <div style={s.actionCard}>
            <h4 style={s.sideTitle}><ShieldCheck size={14} /> PERSISTENCE</h4>
            <p style={s.sideText}>Configuration changes are applied immediately to the AI engine but must be saved to survive system restarts.</p>
            <button type="submit" style={s.saveBtn} disabled={loading}>
              <Save size={16} /> 
              {loading ? 'SYNCHRONIZING...' : 'COMMIT PROTOCOLS'}
            </button>
          </div>

          <div style={s.actionCard}>
            <h4 style={s.sideTitle}><ShieldAlert size={14} /> ALERT LOGIC</h4>
            <div style={s.logicPill}>WEAPONS: 0s COOLDOWN</div>
            <div style={s.logicPill}>INTRUSION: 60s COOLDOWN</div>
            <div style={s.logicPill}>FACE MATCH: 300s COOLDOWN</div>
          </div>
        </aside>
      </form>
    </div>
  )
}

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },
  
  statusBanner: { 
    display: 'flex', alignItems: 'center', gap: '12px', padding: '16px 24px', 
    borderRadius: 'var(--radius-md)', border: '1px solid', 
    fontSize: '0.85rem', fontWeight: 800, letterSpacing: '0.05em' 
  },

  formLayout: { display: 'grid', gridTemplateColumns: '1fr 340px', gap: '32px' },
  mainContent: { display: 'flex', flexDirection: 'column', gap: '24px' },
  
  module: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '32px', transition: 'border-color 0.3s',
    boxShadow: 'var(--shadow-md)'
  },
  moduleHeader: { display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '32px' },
  moduleIcon: { 
    width: '48px', height: '48px', borderRadius: 'var(--radius-md)', 
    background: 'var(--bg-surface-raised)', display: 'flex', 
    alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-bright)' 
  },
  moduleTitle: { margin: 0, fontSize: '1rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '0.05em' },
  moduleDesc: { margin: '6px 0 0', fontSize: '0.8rem', color: 'var(--text-dim)' },
  
  switch: { cursor: 'pointer' },
  switchKnob: { 
    padding: '6px 16px', borderRadius: '20px', fontSize: '0.65rem', 
    fontWeight: 900, color: '#fff', transition: 'all 0.3s', letterSpacing: '0.05em'
  },

  moduleBody: { display: 'flex', flexDirection: 'column', gap: '24px', transition: 'opacity 0.3s' },
  fieldGrid: { display: 'grid', gridTemplateColumns: '1fr 140px', gap: '20px' },
  inputGroup: { display: 'flex', flexDirection: 'column', gap: '8px' },
  label: { fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-dim)', letterSpacing: '0.05em' },
  input: { 
    width: '100%', background: 'var(--bg-app)', border: '1px solid var(--border-base)', 
    color: 'var(--text-main)', padding: '14px', borderRadius: 'var(--radius-md)', 
    fontSize: '0.9rem', outline: 'none', fontFamily: 'inherit', transition: 'border-color 0.2s'
  },
  
  hint: { fontSize: '0.7rem', color: 'var(--text-dim)', fontWeight: 500, marginTop: '-4px' },
  testBtn: {
    alignSelf: 'flex-start', background: 'var(--bg-app)', 
    border: '1px solid var(--border-bright)', color: 'var(--text-main)', 
    padding: '12px 20px', borderRadius: 'var(--radius-md)', cursor: 'pointer', 
    fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', 
    gap: '8px', transition: 'all 0.2s' 
  },

  sidebar: { display: 'flex', flexDirection: 'column', gap: '24px' },
  actionCard: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '24px', 
    boxShadow: 'var(--shadow-md)' 
  },
  sideTitle: { 
    margin: '0 0 16px', fontSize: '0.8rem', fontWeight: 800, 
    color: 'var(--text-sub)', textTransform: 'uppercase', letterSpacing: '0.05em',
    display: 'flex', alignItems: 'center', gap: '8px'
  },
  sideText: { fontSize: '0.8rem', color: 'var(--text-dim)', lineHeight: '1.6', marginBottom: '24px' },
  saveBtn: { 
    width: '100%', background: 'var(--accent-primary)', color: '#fff', 
    border: 'none', padding: '16px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', fontSize: '0.9rem', fontWeight: 800, 
    display: 'flex', alignItems: 'center', justifyContent: 'center', 
    gap: '10px', boxShadow: '0 4px 12px var(--accent-soft)', transition: 'all 0.2s'
  },
  logicPill: { 
    padding: '10px 16px', background: 'var(--bg-app)', 
    border: '1px solid var(--border-base)', borderRadius: 'var(--radius-sm)', 
    fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-dim)', 
    marginBottom: '10px', letterSpacing: '0.05em' 
  },

  loadingBox: { height: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px', color: 'var(--text-dim)', letterSpacing: '2px', fontSize: '0.85rem', fontWeight: 600 },
  spin: { animation: 'spin 2s linear infinite' }
}
