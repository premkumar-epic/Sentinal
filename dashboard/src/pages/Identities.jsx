import { useState, useEffect, useCallback } from 'react'
import { User, Pencil, Check, Trash2, Upload, Fingerprint, Calendar, Eye, MapPin, X, Save } from 'lucide-react'
import useStore, { API_BASE } from '../store/useStore'

export default function Identities() {
  const identities = useStore((s) => s.identities)
  const fetchIdentitiesStore = useStore((s) => s.fetchIdentities)
  const updateIdentityStore = useStore((s) => s.updateIdentity)
  const deleteIdentityStore = useStore((s) => s.deleteIdentity)
  const enrollFaceStore = useStore((s) => s.enrollFace)

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
      await fetchIdentitiesStore()
    } catch (err) {
      setError(`Database synchronization failure: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [fetchIdentitiesStore])

  useEffect(() => {
    fetchIdentities()
    const interval = setInterval(fetchIdentities, 30000)
    return () => clearInterval(interval)
  }, [fetchIdentities])

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
      setToast('ERROR: IDENTIFIER CANNOT BE NULL')
      return
    }
    const success = await updateIdentityStore(globalId, editName.trim())
    if (success) {
      setEditingId(null)
      setEditName('')
      setToast('PROFILE UPDATED')
      fetchIdentities()
    } else {
      setToast('FAUL: UPDATE REJECTED')
    }
  }

  const handleCancelEdit = () => {
    setEditingId(null)
    setEditName('')
  }

  const handleDelete = async (globalId) => {
    if (!window.confirm('PERMANENT ACTION: PURGE SUBJECT PROFILE FROM REGISTRY?')) return
    const success = await deleteIdentityStore(globalId)
    if (success) {
      setToast('PROFILE PURGED')
      fetchIdentities()
    } else {
      setToast('ERROR: PURGE FAILED')
    }
  }

  const handleUploadFace = async (globalId, file) => {
    if (!file) return
    setUploadingId(globalId)
    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', '')

    const success = await enrollFaceStore(globalId, formData)
    setUploadingId(null)
    if (success) {
      setToast('BIOMETRIC ENROLLMENT COMPLETE')
      fetchIdentities()
    } else {
      setToast('ERROR: ENROLLMENT REJECTED')
    }
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>Identity Registry</h2>
          <p style={s.subtitle}>Centralized biometric database and cross-node subject tracking</p>
        </div>
        {toast && (
          <div style={s.toast}>
            <Fingerprint size={14} /> {toast}
          </div>
        )}
      </header>

      {error && <div style={s.errorBanner}>{error}</div>}

      {loading && identities.length === 0 ? (
        <div style={s.statusMsg}>SYNCHRONIZING SUBJECT DATA...</div>
      ) : identities.length === 0 ? (
        <div style={s.emptyState}>
          <Fingerprint size={48} style={{ opacity: 0.2, marginBottom: '16px' }} />
          NO IDENTITIES ENROLLED
        </div>
      ) : (
        <div style={s.grid}>
          {identities.map((identity) => (
            <div key={identity.global_id} style={{
              ...s.card,
              borderColor: identity.enrolled_at ? 'var(--status-success)' : 'var(--glass-border)'
            }}>
              <div style={s.cardTop}>
                <div style={s.avatarContainer}>
                  <div style={s.avatar}>
                    <SnapshotAvatar globalId={identity.global_id} enrolled={!!identity.enrolled_at} />
                  </div>
                  {identity.enrolled_at && <div style={s.enrolledBadge} title="Biometrics Verified" />}
                </div>
                
                <div style={s.cardActions}>
                  {editingId === identity.global_id ? (
                    <>
                      <button style={s.actionBtn} onClick={() => handleSaveName(identity.global_id)}><Save size={16} color="var(--status-success)" /></button>
                      <button style={s.actionBtn} onClick={handleCancelEdit}><X size={16} /></button>
                    </>
                  ) : (
                    <>
                      <button style={s.actionBtn} onClick={() => handleStartEdit(identity)}><Pencil size={14} /></button>
                      <button style={s.actionBtn} onClick={() => handleDelete(identity.global_id)}><Trash2 size={14} color="var(--status-danger)" /></button>
                    </>
                  )}
                </div>
              </div>

              <div style={s.profileBody}>
                {editingId === identity.global_id ? (
                  <div style={s.editContainer}>
                    <input
                      style={s.nameInput}
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onKeyDown={(e) => e.key === 'Enter' && handleSaveName(identity.global_id)}
                      autoFocus
                    />
                  </div>
                ) : (
                  <h3 style={s.subjectName}>
                    {identity.name || `SUBJECT_UNNAMED`}
                    <span className="mono" style={s.subjectUid}>#{identity.global_id.slice(0, 8)}</span>
                  </h3>
                )}

                <div style={s.statsGrid}>
                  <div style={s.statItem}>
                    <div style={s.statLabel}>SIGHTINGS</div>
                    <div style={s.statValue}>{identity.sighting_count}</div>
                  </div>
                  <div style={s.statItem}>
                    <div style={s.statLabel}>STATUS</div>
                    <div style={{ ...s.statValue, color: identity.enrolled_at ? 'var(--status-success)' : 'var(--status-warning)' }}>
                      {identity.enrolled_at ? 'VERIFIED' : 'PENDING'}
                    </div>
                  </div>
                </div>

                <div style={s.metaList}>
                  <div style={s.metaItem}>
                    <Calendar size={12} />
                    <span>LAST DETECTED: {identity.last_seen ? formatDate(identity.last_seen) : 'N/A'}</span>
                  </div>
                  <div style={s.metaItem}>
                    <MapPin size={12} />
                    <span className="mono">NODE: {identity.last_cam || 'UNKNOWN'}</span>
                  </div>
                </div>

                <div style={s.enrollmentSection}>
                  <input
                    type="file"
                    accept="image/*"
                    style={{ display: 'none' }}
                    id={`enroll-${identity.global_id}`}
                    onChange={(e) => {
                      if (e.target.files?.[0]) handleUploadFace(identity.global_id, e.target.files[0])
                      e.target.value = ''
                    }}
                    disabled={uploadingId === identity.global_id}
                  />
                  <button
                    style={uploadingId === identity.global_id ? s.enrollBtnActive : s.enrollBtn}
                    onClick={() => document.getElementById(`enroll-${identity.global_id}`).click()}
                    disabled={uploadingId === identity.global_id}
                  >
                    <Upload size={14} />
                    {uploadingId === identity.global_id ? 'UPLOADING BIOMETRICS...' : 'INITIALIZE ENROLLMENT'}
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SnapshotAvatar({ globalId, enrolled }) {
  const token = useStore((s) => s.token)
  const [failed, setFailed] = useState(false)
  const src = `${API_BASE}/api/snapshots/data/snapshots/identities/${globalId}.jpg${token ? `?token=${token}` : ''}`
  if (failed) {
    return <User size={32} color={enrolled ? 'var(--status-success)' : 'var(--text-dim)'} />
  }
  return (
    <img
      src={src}
      alt="subject"
      onError={() => setFailed(true)}
      style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: 'var(--radius-md)' }}
    />
  )
}

function formatDate(isoString) {
  return new Date(isoString).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false })
}

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },
  
  toast: { 
    background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--status-success)', 
    color: 'var(--status-success)', padding: '10px 20px', borderRadius: 'var(--radius-md)', 
    fontSize: '0.8rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '10px',
    letterSpacing: '0.05em', animation: 'fadeIn 0.2s ease-out', boxShadow: 'var(--shadow-sm)'
  },

  errorBanner: { background: 'rgba(244, 63, 94, 0.1)', border: '1px solid var(--status-danger)', color: 'var(--status-danger)', padding: '16px', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600 },
  statusMsg: { textAlign: 'center', padding: '100px', color: 'var(--text-dim)', fontSize: '0.9rem', letterSpacing: '0.1em', fontWeight: 600 },
  emptyState: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '300px', color: 'var(--text-dim)', fontSize: '0.9rem', letterSpacing: '0.05em', fontWeight: 600 },

  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' },
  card: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '24px', transition: 'transform 0.2s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.2s ease',
    boxShadow: 'var(--shadow-md)'
  },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' },
  avatarContainer: { position: 'relative' },
  avatar: {
    width: '72px', height: '72px', background: 'var(--bg-surface-raised)',
    borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center',
    justifyContent: 'center', border: '1px solid var(--border-bright)',
    overflow: 'hidden',
  },
  enrolledBadge: { 
    position: 'absolute', bottom: '-4px', right: '-4px', width: '16px', height: '16px', 
    background: 'var(--status-success)', borderRadius: '50%', border: '3px solid var(--bg-surface)',
    boxShadow: '0 0 12px var(--status-success)'
  },
  cardActions: { display: 'flex', gap: '6px' },
  actionBtn: { background: 'var(--bg-app)', border: '1px solid var(--border-base)', color: 'var(--text-sub)', cursor: 'pointer', padding: '8px', borderRadius: 'var(--radius-md)', transition: 'all 0.2s', display: 'flex', alignItems: 'center', justifyContent: 'center' },

  profileBody: { display: 'flex', flexDirection: 'column', gap: '20px' },
  subjectName: { margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-main)', display: 'flex', flexDirection: 'column', gap: '4px', letterSpacing: '-0.01em' },
  subjectUid: { fontSize: '0.75rem', color: 'var(--text-dim)', fontWeight: 600, letterSpacing: '0.05em' },
  
  editContainer: { width: '100%' },
  nameInput: { 
    width: '100%', background: 'var(--bg-app)', border: '1px solid var(--accent-primary)', 
    color: 'var(--text-main)', padding: '12px 16px', borderRadius: 'var(--radius-md)', fontSize: '0.95rem', 
    outline: 'none', fontFamily: 'inherit', fontWeight: 600, boxShadow: '0 0 0 3px var(--accent-soft)'
  },

  statsGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', padding: '16px', background: 'var(--bg-app)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-base)' },
  statItem: { display: 'flex', flexDirection: 'column', gap: '4px' },
  statLabel: { fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-dim)', letterSpacing: '0.05em' },
  statValue: { fontSize: '1rem', fontWeight: 900, color: 'var(--text-main)' },

  metaList: { display: 'flex', flexDirection: 'column', gap: '8px' },
  metaItem: { display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.75rem', color: 'var(--text-sub)', fontWeight: 600 },

  enrollmentSection: { marginTop: '8px' },
  enrollBtn: { 
    width: '100%', padding: '12px', background: 'var(--bg-surface-raised)', 
    border: '1px dashed var(--border-bright)', color: 'var(--text-main)', 
    borderRadius: 'var(--radius-md)', cursor: 'pointer', fontSize: '0.8rem', 
    fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center', 
    gap: '10px', transition: 'all 0.2s' 
  },
  enrollBtnActive: { 
    width: '100%', padding: '12px', background: 'var(--status-success)', 
    border: 'none', color: '#ffffff', borderRadius: 'var(--radius-md)', 
    fontSize: '0.8rem', fontWeight: 800, display: 'flex', alignItems: 'center', 
    justifyContent: 'center', gap: '10px', boxShadow: '0 4px 12px rgba(16,185,129,0.3)'
  }
}
