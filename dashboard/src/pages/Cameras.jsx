import { useState, useEffect, useCallback } from 'react'
import { Video, Plus, RefreshCw, Trash2, Globe, Calendar, CheckCircle2, XCircle, Settings2, Edit2 } from 'lucide-react'
import useStore from '../store/useStore'

export default function Cameras() {
  const cameras = useStore((s) => s.cameras)
  const fetchCamerasStore = useStore((s) => s.fetchCameras)
  const addCamera = useStore((s) => s.addCamera)
  const deleteCamera = useStore((s) => s.deleteCamera)
  const patchCamera = useStore((s) => s.patchCamera)

  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Add/Edit form state
  const [form, setForm] = useState({ cam_id: '', url: '', label: '' })
  const [editingId, setEditingId] = useState(null)
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)

  const fetchCameras = useCallback(async () => {
    setLoading(true)
    try {
      await fetchCamerasStore()
      setError('')
    } catch (err) {
      setError(`Failed to load cameras: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [fetchCamerasStore])

  useEffect(() => {
    fetchCameras()
    const interval = setInterval(fetchCameras, 10000)
    return () => clearInterval(interval)
  }, [fetchCameras])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.cam_id.trim() || !form.url.trim()) {
      setAddError('Primary identifiers (ID/URL) are mandatory.')
      return
    }
    setAdding(true)
    setAddError('')
    try {
      if (editingId) {
        const success = await patchCamera(editingId, {
          url: form.url.trim(),
          label: form.label.trim() || undefined,
        })
        if (!success) {
          setAddError('Failed to update camera configuration.')
          return
        }
      } else {
        const res = await addCamera({
          cam_id: form.cam_id.trim(),
          url: form.url.trim(),
          label: form.label.trim() || undefined,
        })
        
        if (res.status === 409) {
          setAddError(`System Conflict: ID "${form.cam_id}" is already registered.`)
          return
        }
        
        if (!res.ok) {
          const body = await res.json().catch(() => ({}))
          setAddError(body.detail || `Protocol Error ${res.status}`)
          return
        }
      }
      
      setForm({ cam_id: '', url: '', label: '' })
      setEditingId(null)
      await fetchCameras()
    } catch (err) {
      setAddError(`Link Failure: ${err.message}`)
    } finally {
      setAdding(false)
    }
  }

  const startEdit = (cam) => {
    setEditingId(cam.cam_id)
    setForm({
      cam_id: cam.cam_id,
      url: cam.url,
      label: cam.label || ''
    })
    setAddError('')
    // Scroll to form if needed
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const cancelEdit = () => {
    setEditingId(null)
    setForm({ cam_id: '', url: '', label: '' })
    setAddError('')
  }

  const handleDelete = async (cam_id) => {
    if (!window.confirm(`PERMANENT ACTION: Deregister camera "${cam_id}" and terminate its AI pipeline?`)) return
    try {
      const success = await deleteCamera(cam_id)
      if (!success) {
        alert(`De-registration failed. Protocol error.`)
        return
      }
      await fetchCameras()
    } catch (err) {
      alert(`System fault during deletion: ${err.message}`)
    }
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>System Nodes</h2>
          <p style={s.subtitle}>Register and monitor hardware capture endpoints</p>
        </div>
        <button style={s.refreshBtn} onClick={fetchCameras} disabled={loading}>
          <RefreshCw size={14} style={loading ? s.spin : {}} />
          {loading ? 'SYNCHRONIZING...' : 'REFRESH STATUS'}
        </button>
      </header>

      <div style={s.contentLayout}>
        {/* Registration Terminal */}
        <section style={s.formSection}>
          <div style={s.card}>
            <div style={s.cardHeader}>
              {editingId ? <Edit2 size={18} color="var(--accent-primary)" /> : <Plus size={18} color="var(--accent-primary)" />}
              <h3 style={s.cardTitle}>{editingId ? 'Update Node Config' : 'Register New Node'}</h3>
            </div>
            <form onSubmit={handleAdd} style={s.form}>
              <div style={s.inputGroup}>
                <label style={s.label}>NODE IDENTIFIER {editingId && '(IMMUTABLE)'}</label>
                <input
                  style={{...s.input, opacity: editingId ? 0.5 : 1}}
                  placeholder="cam_alpha_01"
                  value={form.cam_id}
                  onChange={(e) => setForm((f) => ({ ...f, cam_id: e.target.value }))}
                  disabled={adding || !!editingId}
                />
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>CAPTURE PROTOCOL / URL</label>
                <input
                  style={s.input}
                  placeholder="rtsp://192.168.1.x:554/live"
                  value={form.url}
                  onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
                  disabled={adding}
                />
              </div>

              <div style={s.inputGroup}>
                <label style={s.label}>FRIENDLY LABEL</label>
                <input
                  style={s.input}
                  placeholder="Main Entrance"
                  value={form.label}
                  onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
                  disabled={adding}
                />
              </div>

              {addError && <p style={s.err}>{addError}</p>}

              <div style={{ display: 'flex', gap: '12px' }}>
                <button style={{...s.addBtn, flex: 1}} type="submit" disabled={adding}>
                  {adding ? 'AUTHORIZING...' : (editingId ? 'SAVE CHANGES' : 'INITIALIZE REGISTRATION')}
                </button>
                {editingId && (
                  <button style={s.cancelBtn} type="button" onClick={cancelEdit} disabled={adding}>
                    CANCEL
                  </button>
                )}
              </div>
            </form>
          </div>
        </section>

        {/* Node Registry */}
        <section style={s.listSection}>
          <div style={s.card}>
            <div style={s.cardHeader}>
              <Video size={18} color="var(--text-secondary)" />
              <h3 style={s.cardTitle}>Node Registry</h3>
            </div>

            {error && <p style={s.err}>{error}</p>}

            <div style={s.nodeList}>
              {cameras.length === 0 ? (
                <div style={s.emptyState}>
                  <Settings2 size={32} style={{ marginBottom: '12px', opacity: 0.3 }} />
                  NO NODES REGISTERED
                </div>
              ) : (
                cameras.map((cam) => (
                  <div key={cam.cam_id} style={s.nodeItem}>
                    <div style={s.nodeInfo}>
                      <div style={s.statusIcon}>
                        {cam.alive ? (
                          <CheckCircle2 size={20} color="var(--status-success)" />
                        ) : (
                          <XCircle size={20} color="var(--status-danger)" />
                        )}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={s.nodeNameRow}>
                          <span style={s.nodeLabel}>{cam.label || 'Unnamed Node'}</span>
                          <span style={s.nodeId} className="mono">[{cam.cam_id}]</span>
                        </div>
                        <div style={s.nodeMeta}>
                          <span style={s.metaItem}><Globe size={12} /> {cam.url}</span>
                          <span style={s.metaItem}><Calendar size={12} /> {cam.added_at ? new Date(cam.added_at).toLocaleDateString() : 'Unknown'}</span>
                        </div>
                      </div>
                    </div>
                    <div style={s.nodeActions}>
                      <button 
                        style={s.editBtn} 
                        onClick={() => startEdit(cam)}
                        title="Edit Configuration"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button 
                        style={s.deleteBtn} 
                        onClick={() => handleDelete(cam.cam_id)}
                        title="Deregister"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },
  
  refreshBtn: { 
    display: 'flex', alignItems: 'center', gap: '8px', 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    color: 'var(--text-main)', padding: '10px 16px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, transition: 'all 0.2s',
    boxShadow: 'var(--shadow-sm)'
  },
  spin: { animation: 'spin 2s linear infinite' },

  contentLayout: { display: 'grid', gridTemplateColumns: '400px 1fr', gap: '32px' },
  card: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '32px', 
    boxShadow: 'var(--shadow-md)', height: '100%' 
  },
  cardHeader: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' },
  cardTitle: { margin: 0, fontSize: '0.9rem', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase', letterSpacing: '0.05em' },
  
  form: { display: 'flex', flexDirection: 'column', gap: '24px' },
  inputGroup: { display: 'flex', flexDirection: 'column', gap: '10px' },
  label: { fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.05em' },
  input: { 
    background: 'var(--bg-app)', border: '1px solid var(--border-base)', 
    color: 'var(--text-main)', padding: '14px', borderRadius: 'var(--radius-md)', 
    fontSize: '0.9rem', outline: 'none', transition: 'all 0.2s', 
    fontFamily: 'inherit' 
  },
  addBtn: { 
    background: 'var(--accent-primary)', 
    color: '#fff', border: 'none', padding: '16px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', fontSize: '0.9rem', fontWeight: 700, marginTop: '8px', 
    boxShadow: '0 4px 12px var(--accent-soft)', transition: 'all 0.2s'
  },
  
  nodeList: { display: 'flex', flexDirection: 'column', gap: '16px' },
  nodeItem: { 
    display: 'flex', alignItems: 'center', justifyContent: 'space-between', 
    padding: '20px', background: 'var(--bg-app)', borderRadius: 'var(--radius-md)', 
    border: '1px solid var(--border-base)', transition: 'all 0.2s',
    cursor: 'default'
  },
  nodeInfo: { display: 'flex', alignItems: 'center', gap: '20px', flex: 1 },
  statusIcon: { width: '48px', height: '48px', background: 'var(--bg-surface-raised)', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-bright)' },
  nodeNameRow: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' },
  nodeLabel: { fontWeight: 700, color: 'var(--text-main)', fontSize: '1.05rem' },
  nodeId: { fontSize: '0.75rem', color: 'var(--text-dim)' },
  nodeMeta: { display: 'flex', gap: '20px', fontSize: '0.75rem', color: 'var(--text-sub)' },
  metaItem: { display: 'flex', alignItems: 'center', gap: '6px' },
  
  nodeActions: { display: 'flex', gap: '8px' },
  editBtn: { 
    background: 'transparent', border: '1px solid transparent', 
    color: 'var(--text-sub)', padding: '10px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', transition: 'all 0.2s' 
  },
  cancelBtn: {
    background: 'transparent', border: '1px solid var(--border-base)',
    color: 'var(--text-sub)', padding: '16px 24px', borderRadius: 'var(--radius-md)',
    cursor: 'pointer', fontSize: '0.9rem', fontWeight: 700, marginTop: '8px', transition: 'all 0.2s'
  },
  deleteBtn: { 
    background: 'transparent', border: '1px solid transparent', 
    color: 'var(--text-dim)', padding: '10px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', transition: 'all 0.2s' 
  },
  err: { color: 'var(--status-danger)', fontSize: '0.8rem', fontWeight: 600, background: 'rgba(244, 63, 94, 0.1)', border: '1px solid rgba(244, 63, 94, 0.2)', padding: '12px', borderRadius: 'var(--radius-md)' },
  emptyState: { 
    height: '200px', display: 'flex', flexDirection: 'column', 
    alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)', 
    fontSize: '0.85rem', fontWeight: 600, letterSpacing: '0.05em',
    background: 'var(--glass-bg)', borderRadius: 'var(--radius-md)', border: '1px dashed var(--border-bright)'
  }
}
