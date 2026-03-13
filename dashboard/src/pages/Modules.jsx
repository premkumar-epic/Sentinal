import React, { useEffect, useState } from 'react'
import useStore from '../store/useStore'
import { Cpu, Settings, Power, CheckCircle2, XCircle, Info, Sliders } from 'lucide-react'

export default function Modules() {
  const { modules, fetchModules, updateModule } = useStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchModules().finally(() => setLoading(false))
  }, [fetchModules])

  const handleToggle = async (moduleId, currentEnabled) => {
    await updateModule(moduleId, { enabled: !currentEnabled })
  }

  const handleUpdateConfig = async (moduleId, config) => {
    await updateModule(moduleId, { config })
  }

  if (loading) {
    return <div style={s.loading}>Scanning system modules...</div>
  }

  return (
    <div style={s.container}>
      <header style={s.header}>
        <div>
          <h1 style={s.title}>Detection Modules</h1>
          <p style={s.subtitle}>Configure specialized AI models and detection logic</p>
        </div>
        <div style={s.cpuStats}>
          <Cpu size={18} />
          <span>Active Engines: {modules.filter(m => m.enabled && m.loaded).length}</span>
        </div>
      </header>

      <div style={s.grid}>
        {modules.map((m) => (
          <ModuleCard 
            key={m.module_id} 
            module={m} 
            onToggle={() => handleToggle(m.module_id, m.enabled)}
            onUpdateConfig={(config) => handleUpdateConfig(m.module_id, config)}
          />
        ))}
      </div>
    </div>
  )
}

function ModuleCard({ module, onToggle, onUpdateConfig }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const m = module

  return (
    <div style={{...s.card, borderColor: m.enabled ? 'var(--accent-primary)' : 'var(--border-base)'}}>
      <div style={s.cardTop}>
        <div style={s.iconWrap}>
          <Cpu size={24} color={m.enabled ? 'var(--accent-primary)' : 'var(--text-dim)'} />
        </div>
        <div style={s.info}>
          <h3 style={s.moduleName}>{m.display_name}</h3>
          <div style={s.statusRow}>
            <span style={{...s.badge, color: m.enabled ? '#30d158' : '#ff453a', background: m.enabled ? 'rgba(48, 209, 88, 0.1)' : 'rgba(255, 69, 58, 0.1)'}}>
              {m.enabled ? 'Enabled' : 'Disabled'}
            </span>
            {m.requires_model && (
              <span style={{...s.badge, color: m.loaded ? '#30d158' : '#ff9f0a', background: 'rgba(255, 255, 255, 0.05)'}}>
                {m.loaded ? 'Model Loaded' : 'Awaiting Model'}
              </span>
            )}
          </div>
        </div>
        <button 
          onClick={onToggle}
          style={{...s.toggleBtn, background: m.enabled ? 'var(--accent-primary)' : 'rgba(255,255,255,0.05)'}}
        >
          <Power size={18} />
        </button>
      </div>

      <p style={s.description}>{m.description}</p>

      <div style={s.cardActions}>
        <button style={s.actionBtn} onClick={() => setIsExpanded(!isExpanded)}>
          <Sliders size={14} />
          <span>Configure</span>
        </button>
      </div>

      {isExpanded && (
        <div style={s.configPanel}>
          {Object.entries(m.config).map(([key, val]) => (
            <div key={key} style={s.configRow}>
              <label style={s.configLabel}>{key.replace(/_/g, ' ')}</label>
              <ConfigInput 
                val={val} 
                onSave={(newVal) => onUpdateConfig({ ...m.config, [key]: newVal })} 
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ConfigInput({ val, onSave }) {
  const [local, setLocal] = useState(val)

  useEffect(() => { setLocal(val) }, [val])

  if (typeof val === 'number') {
    return (
      <div style={{display: 'flex', gap: '10px', alignItems: 'center', flex: 1}}>
        <input 
          type="range" min="0" max="1" step="0.05" 
          value={local} 
          onChange={(e) => setLocal(parseFloat(e.target.value))}
          onMouseUp={() => onSave(local)}
          style={{flex: 1}}
        />
        <span style={{fontSize: '0.8rem', width: '30px'}}>{local.toFixed(2)}</span>
      </div>
    )
  }

  if (Array.isArray(val)) {
    return (
      <input 
        style={s.textInput}
        value={local.join(', ')} 
        onChange={(e) => setLocal(e.target.value.split(',').map(s => s.trim()))}
        onBlur={() => onSave(local)}
      />
    )
  }

  return (
    <input 
      style={s.textInput}
      value={local} 
      onChange={(e) => setLocal(e.target.value)}
      onBlur={() => onSave(local)}
    />
  )
}

const s = {
  container: { padding: '40px', maxWidth: '1200px', margin: '0 auto' },
  loading: { textAlign: 'center', padding: '100px', color: 'var(--text-dim)', fontSize: '1.2rem', fontWeight: 600 },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '40px' },
  title: { fontSize: '2rem', fontWeight: 800, margin: 0, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { color: 'var(--text-dim)', marginTop: '8px', fontSize: '1rem', fontWeight: 500 },
  cpuStats: { 
    display: 'flex', alignItems: 'center', gap: '10px', 
    background: 'rgba(255,255,255,0.03)', padding: '12px 20px', 
    borderRadius: '12px', border: '1px solid var(--border-base)',
    fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-primary)'
  },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' },
  card: {
    background: 'var(--bg-surface)',
    borderRadius: 'var(--radius-lg)',
    border: '1px solid var(--border-base)',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    transition: 'all 0.3s ease',
  },
  cardTop: { display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '16px' },
  iconWrap: { 
    width: '48px', height: '48px', borderRadius: '12px', 
    background: 'rgba(255,255,255,0.03)', display: 'flex', 
    alignItems: 'center', justifyContent: 'center' 
  },
  info: { flex: 1 },
  moduleName: { fontSize: '1.1rem', fontWeight: 700, margin: 0, color: 'var(--text-main)' },
  statusRow: { display: 'flex', gap: '8px', marginTop: '6px' },
  badge: { fontSize: '0.65rem', fontWeight: 800, padding: '2px 8px', borderRadius: '6px', textTransform: 'uppercase' },
  toggleBtn: { 
    width: '40px', height: '40px', borderRadius: '10px', 
    border: 'none', color: '#fff', cursor: 'pointer',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    transition: 'all 0.2s ease'
  },
  description: { fontSize: '0.9rem', color: 'var(--text-sub)', lineHeight: 1.5, margin: '16px 0', flex: 1 },
  cardActions: { borderTop: '1px solid var(--border-base)', paddingTop: '16px', marginTop: 'auto' },
  actionBtn: { 
    background: 'transparent', border: 'none', color: 'var(--text-dim)', 
    display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer',
    fontSize: '0.8rem', fontWeight: 600, transition: 'color 0.2s'
  },
  configPanel: { 
    background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '16px', 
    marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' 
  },
  configRow: { display: 'flex', flexDirection: 'column', gap: '8px' },
  configLabel: { fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-dim)', textTransform: 'uppercase' },
  textInput: { 
    background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-base)', 
    borderRadius: '6px', padding: '8px 12px', color: '#fff', fontSize: '0.85rem' 
  }
}
