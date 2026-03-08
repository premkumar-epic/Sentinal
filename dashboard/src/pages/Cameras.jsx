import { useState, useEffect, useCallback } from 'react'
import { API_BASE } from '../store/useStore'

export default function Cameras() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Add form state
  const [form, setForm] = useState({ cam_id: '', url: '', label: '' })
  const [addError, setAddError] = useState('')
  const [adding, setAdding] = useState(false)

  const fetchCameras = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/api/cameras`)
      if (!res.ok) throw new Error(res.statusText)
      setCameras(await res.json())
      setError('')
    } catch (err) {
      setError(`Failed to load cameras: ${err.message}`)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchCameras()
    const interval = setInterval(fetchCameras, 10000)
    return () => clearInterval(interval)
  }, [fetchCameras])

  const handleAdd = async (e) => {
    e.preventDefault()
    if (!form.cam_id.trim() || !form.url.trim()) {
      setAddError('Camera ID and URL are required.')
      return
    }
    setAdding(true)
    setAddError('')
    try {
      const res = await fetch(`${API_BASE}/api/cameras`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cam_id: form.cam_id.trim(),
          url: form.url.trim(),
          label: form.label.trim() || undefined,
        }),
      })
      if (res.status === 409) {
        setAddError(`Camera ID "${form.cam_id}" already exists.`)
        return
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        setAddError(body.detail || `Error ${res.status}`)
        return
      }
      setForm({ cam_id: '', url: '', label: '' })
      await fetchCameras()
    } catch (err) {
      setAddError(`Request failed: ${err.message}`)
    } finally {
      setAdding(false)
    }
  }

  const handleDelete = async (cam_id) => {
    if (!window.confirm(`Remove camera "${cam_id}"? This stops its pipeline.`)) return
    try {
      const res = await fetch(`${API_BASE}/api/cameras/${cam_id}`, { method: 'DELETE' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        alert(body.detail || `Failed to remove camera (${res.status})`)
        return
      }
      await fetchCameras()
    } catch (err) {
      alert(`Request failed: ${err.message}`)
    }
  }

  return (
    <div style={s.root}>
      <h2 style={s.title}>Camera Management</h2>

      {/* Add Camera form */}
      <div style={s.card}>
        <h3 style={s.cardTitle}>Add Camera</h3>
        <form onSubmit={handleAdd} style={s.form}>
          <label style={s.label}>Camera ID</label>
          <input
            style={s.input}
            placeholder="e.g. cam_0"
            value={form.cam_id}
            onChange={(e) => setForm((f) => ({ ...f, cam_id: e.target.value }))}
            disabled={adding}
          />

          <label style={s.label}>Stream URL</label>
          <input
            style={s.input}
            placeholder="http://192.168.1.x:8080/video  or  rtsp://..."
            value={form.url}
            onChange={(e) => setForm((f) => ({ ...f, url: e.target.value }))}
            disabled={adding}
          />

          <label style={s.label}>Label (optional)</label>
          <input
            style={s.input}
            placeholder="Front Door"
            value={form.label}
            onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
            disabled={adding}
          />

          {addError && <p style={s.err}>{addError}</p>}

          <button style={s.addBtn} type="submit" disabled={adding}>
            {adding ? 'Adding…' : '+ Add Camera'}
          </button>
        </form>
      </div>

      {/* Camera list */}
      <div style={s.card}>
        <div style={s.cardHeaderRow}>
          <h3 style={s.cardTitle}>Active Cameras</h3>
          <button style={s.refreshBtn} onClick={fetchCameras} disabled={loading}>
            {loading ? '…' : '↻ Refresh'}
          </button>
        </div>

        {error && <p style={s.err}>{error}</p>}

        {cameras.length === 0 ? (
          <p style={s.empty}>
            {loading ? 'Loading…' : 'No cameras added yet. Use the form above to add one.'}
          </p>
        ) : (
          <div style={s.tableWrap}>
            <table style={s.table}>
              <thead>
                <tr>
                  {['Status', 'ID', 'Label', 'URL', 'Added', ''].map((h) => (
                    <th key={h} style={s.th}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cameras.map((cam) => (
                  <tr key={cam.cam_id} style={s.tr}>
                    <td style={s.td}>
                      <span style={cam.alive ? s.dotGreen : s.dotRed} title={cam.alive ? 'Connected' : 'Disconnected'} />
                    </td>
                    <td style={s.td}><code style={s.code}>{cam.cam_id}</code></td>
                    <td style={s.td}>{cam.label || '—'}</td>
                    <td style={{ ...s.td, ...s.urlCell }}>{cam.url}</td>
                    <td style={s.td}>
                      {cam.added_at ? new Date(cam.added_at).toLocaleString() : '—'}
                    </td>
                    <td style={s.td}>
                      <button
                        style={s.deleteBtn}
                        onClick={() => handleDelete(cam.cam_id)}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

const s = {
  root: { padding: '16px', background: '#0d0d0d', minHeight: '100vh', color: '#e0e0e0', fontFamily: 'monospace' },
  title: { margin: '0 0 16px', color: '#00e5ff', fontSize: '1.1rem' },
  card: { background: '#1a1a1a', border: '1px solid #333', borderRadius: '6px', padding: '16px', marginBottom: '16px' },
  cardTitle: { margin: '0 0 12px', fontSize: '0.9rem', color: '#aaa' },
  cardHeaderRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' },
  form: { display: 'grid', gridTemplateColumns: '1fr', gap: '6px', maxWidth: '480px' },
  label: { fontSize: '0.75rem', color: '#777', marginTop: '4px' },
  input: { background: '#111', border: '1px solid #444', color: '#e0e0e0', padding: '6px 10px', borderRadius: '3px', fontSize: '0.85rem', outline: 'none' },
  addBtn: { marginTop: '8px', padding: '7px 18px', background: '#00e5ff', color: '#000', border: 'none', borderRadius: '3px', cursor: 'pointer', fontSize: '0.85rem', fontWeight: 'bold', width: 'fit-content' },
  refreshBtn: { padding: '3px 10px', background: '#2a2a2a', color: '#aaa', border: '1px solid #444', borderRadius: '3px', cursor: 'pointer', fontSize: '0.75rem' },
  err: { color: '#ff5252', fontSize: '0.8rem', margin: '4px 0' },
  empty: { color: '#555', fontSize: '0.85rem', margin: '8px 0' },
  tableWrap: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' },
  th: { padding: '6px 8px', background: '#111', color: '#777', textAlign: 'left', borderBottom: '1px solid #333', whiteSpace: 'nowrap' },
  tr: { borderBottom: '1px solid #222' },
  td: { padding: '6px 8px', verticalAlign: 'middle' },
  urlCell: { color: '#aaa', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  code: { background: '#111', padding: '1px 5px', borderRadius: '2px', color: '#00e5ff' },
  dotGreen: { display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#00e676' },
  dotRed: { display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%', background: '#ff1744' },
  deleteBtn: { padding: '3px 10px', background: '#2a0000', color: '#ff5252', border: '1px solid #ff1744', borderRadius: '3px', cursor: 'pointer', fontSize: '0.75rem' },
}
