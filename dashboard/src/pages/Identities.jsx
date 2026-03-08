import { useState, useEffect, useCallback } from 'react'
import { User, Pencil, Check, Trash2, Upload } from 'lucide-react'
import { API_BASE } from '../store/useStore'

export default function Identities() {
  const [identities, setIdentities] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [uploadingId, setUploadingId] = useState(null)
  const [toast, setToast] = useState('')

  const fetchIdentities = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_BASE}/api/identities`)
      if (!res.ok) throw new Error(res.statusText)
      setIdentities(await res.json())
    } catch (err) {
      setError(`Failed to load identities: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchIdentities()
    const interval = setInterval(fetchIdentities, 30000)
    return () => clearInterval(interval)
  }, [fetchIdentities])

  // Auto-clear toast after 3s
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(''), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  const handleStartEdit = (identity) => {
    setEditingId(identity.global_id)
    setEditName(identity.name || '')
  }

  const handleSaveName = async (globalId) => {
    if (editName.trim() === '') {
      setToast('Name cannot be empty')
      return
    }
    try {
      const res = await fetch(`${API_BASE}/api/identities/${globalId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName.trim() }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setToast(body.detail || `Error ${res.status}`)
        return
      }
      setEditingId(null)
      setEditName('')
      setToast('Identity updated')
      await fetchIdentities()
    } catch (err) {
      setToast(`Request failed: ${err.message}`)
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditName('')
  }

  const handleDelete = async (globalId) => {
    if (!window.confirm('Delete this identity?')) return
    try {
      const res = await fetch(`${API_BASE}/api/identities/${globalId}`, {
        method: 'DELETE',
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setToast(body.detail || `Error ${res.status}`)
        return
      }
      setToast('Identity deleted')
      await fetchIdentities()
    } catch (err) {
      setToast(`Request failed: ${err.message}`)
    }
  }

  const handleUploadFace = async (globalId, file) => {
    if (!file) return
    setUploadingId(globalId)
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('name', '')

      const res = await fetch(`${API_BASE}/api/identities/${globalId}/enroll`, {
        method: 'POST',
        body: formData,
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setToast(body.detail || `Error ${res.status}`)
        setUploadingId(null)
        return
      }
      setToast('Face enrolled successfully')
      setUploadingId(null)
      await fetchIdentities()
    } catch (err) {
      setToast(`Request failed: ${err.message}`)
      setUploadingId(null)
    }
  }

  return (
    <div style={s.root}>
      <h2 style={s.title}>Identities</h2>

      {error && <p style={s.errBanner}>{error}</p>}
      {toast && <p style={s.toastBanner}>{toast}</p>}

      {loading && identities.length === 0 ? (
        <p style={s.dim}>Loading identities…</p>
      ) : identities.length === 0 ? (
        <p style={s.empty}>No identities yet. Persons are added automatically when detected.</p>
      ) : (
        <div style={s.grid}>
          {identities.map((identity) => (
            <div key={identity.global_id} style={s.card}>
              <div style={s.cardTop}>
                <div style={s.iconCircle}>
                  <User size={20} color="#00e5ff" />
                </div>
                <div style={s.actions}>
                  {editingId === identity.global_id ? (
                    <>
                      <button
                        style={s.iconBtn}
                        onClick={() => handleSaveName(identity.global_id)}
                        title="Save"
                      >
                        <Check size={16} color="#00e676" />
                      </button>
                      <button
                        style={s.iconBtn}
                        onClick={handleCancelEdit}
                        title="Cancel"
                      >
                        ✕
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        style={s.iconBtn}
                        onClick={() => handleStartEdit(identity)}
                        title="Edit name"
                      >
                        <Pencil size={14} color="#aaa" />
                      </button>
                      <button
                        style={s.iconBtn}
                        onClick={() => handleDelete(identity.global_id)}
                        title="Delete"
                      >
                        <Trash2 size={14} color="#ff5252" />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {editingId === identity.global_id ? (
                <input
                  style={s.nameInput}
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveName(identity.global_id)
                    if (e.key === 'Escape') handleCancelEdit()
                  }}
                  autoFocus
                  placeholder="Enter name"
                />
              ) : (
                <h3 style={s.name}>
                  {identity.name || `Unknown #${identity.global_id.slice(0, 6)}`}
                </h3>
              )}

              <div style={s.badge}>{identity.sighting_count} sightings</div>

              <div style={s.meta}>
                {identity.last_seen && (
                  <p style={s.metaLine}>
                    Last seen: <span style={s.metaValue}>{formatDate(identity.last_seen)}</span>
                  </p>
                )}
                {identity.last_cam && (
                  <p style={s.metaLine}>
                    Camera: <span style={s.metaValue}>{identity.last_cam}</span>
                  </p>
                )}
                {identity.enrolled_at && (
                  <p style={s.metaLine}>
                    Enrolled: <span style={s.metaValue}>{formatDate(identity.enrolled_at)}</span>
                  </p>
                )}
              </div>

              <div style={s.uploadSection}>
                <input
                  type="file"
                  accept="image/*"
                  style={{ display: 'none' }}
                  id={`upload-${identity.global_id}`}
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      handleUploadFace(identity.global_id, e.target.files[0])
                    }
                    e.target.value = ''
                  }}
                  disabled={uploadingId === identity.global_id}
                />
                <button
                  style={s.uploadBtn}
                  onClick={() => document.getElementById(`upload-${identity.global_id}`).click()}
                  disabled={uploadingId === identity.global_id}
                >
                  <Upload size={14} style={{ marginRight: '4px' }} />
                  {uploadingId === identity.global_id ? 'Uploading…' : 'Upload Face'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function formatDate(isoString) {
  const date = new Date(isoString)
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

const s = {
  root: { padding: '16px', background: '#0d0d0d', minHeight: '100vh', color: '#e0e0e0', fontFamily: 'monospace' },
  title: { margin: '0 0 16px', color: '#00e5ff', fontSize: '1.1rem' },
  errBanner: { background: '#330000', border: '1px solid #ff5252', color: '#ff5252', padding: '8px 12px', borderRadius: '4px', marginBottom: '12px', fontSize: '0.85rem' },
  toastBanner: { background: '#003300', border: '1px solid #00e676', color: '#00e676', padding: '8px 12px', borderRadius: '4px', marginBottom: '12px', fontSize: '0.85rem' },
  dim: { color: '#555', fontSize: '0.85rem' },
  empty: { color: '#555', fontSize: '0.85rem', textAlign: 'center', margin: '48px 0' },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' },
  card: { background: '#1a1a1a', border: '1px solid #333', borderRadius: '8px', padding: '16px', position: 'relative' },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' },
  iconCircle: { width: '48px', height: '48px', borderRadius: '50%', background: '#2a2a2a', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 },
  actions: { display: 'flex', gap: '4px' },
  iconBtn: { background: 'none', border: 'none', color: '#aaa', cursor: 'pointer', padding: '4px', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  name: { margin: '0 0 8px', fontSize: '1rem', color: '#e0e0e0' },
  nameInput: { width: '100%', background: '#111', border: '1px solid #444', color: '#e0e0e0', padding: '6px 8px', borderRadius: '4px', fontSize: '0.9rem', marginBottom: '8px', outline: 'none', boxSizing: 'border-box' },
  badge: { display: 'inline-block', background: '#2a3a00', border: '1px solid #558800', color: '#aaf000', fontSize: '0.7rem', padding: '2px 8px', borderRadius: '12px', marginBottom: '8px' },
  meta: { fontSize: '0.75rem', margin: '8px 0' },
  metaLine: { margin: '2px 0', color: '#777' },
  metaValue: { color: '#aaa' },
  uploadSection: { marginTop: '12px' },
  uploadBtn: { width: '100%', padding: '6px 10px', background: '#1a3a1a', border: '1px solid #558844', color: '#00e676', borderRadius: '4px', cursor: 'pointer', fontSize: '0.8rem', display: 'flex', alignItems: 'center', justifyContent: 'center' },
}
