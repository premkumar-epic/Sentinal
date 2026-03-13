import { create } from 'zustand'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws/live'

let wsInstance = null
let reconnectTimer = null
let reconnectDelay = 1000

function connectWebSocket(set, get) {
  if (wsInstance) return

  const token = get().token
  const url = token ? `${WS_URL}?token=${token}` : WS_URL
  wsInstance = new WebSocket(url)

  wsInstance.onopen = () => {
    set({ wsConnected: true })
    reconnectDelay = 1000
  }

  wsInstance.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data)
      if (msg.type === 'weapon_alarm') {
        set({ weaponAlarm: msg })
      } else {
        set((state) => ({ events: [msg, ...state.events].slice(0, 100) }))
        // Fire in-app toast for all alert events
        if (msg.type === 'alert' && msg.alert_type) {
          const alertLabels = {
            intrusion: 'INTRUSION DETECTED',
            loitering: 'LOITERING DETECTED',
            crowding: 'CROWD THRESHOLD EXCEEDED',
            violence: 'VIOLENCE DETECTED',
            face_match: 'FACE MATCH',
            identity_registered: 'NEW IDENTITY',
          }
          const severity = ['violence', 'intrusion'].includes(msg.alert_type) ? 'danger' : 'warning'
          get().addToast({
            title: alertLabels[msg.alert_type] || msg.alert_type.toUpperCase(),
            message: `${msg.cam_id}${msg.zone_label ? ' — ' + msg.zone_label : ''}${msg.name ? ' — ' + msg.name : ''}`,
            severity,
            timestamp: msg.timestamp,
          })
        }
      }
    } catch (_) {}
  }

  wsInstance.onclose = () => {
    wsInstance = null
    set({ wsConnected: false })
    reconnectTimer = setTimeout(() => {
      reconnectDelay = Math.min(reconnectDelay * 2, 30000)
      connectWebSocket(set, get)
    }, reconnectDelay)
  }

  wsInstance.onerror = () => {
    wsInstance?.close()
  }
}

const useStore = create((set, get) => ({
  token: localStorage.getItem('sentinal_token'),
  theme: localStorage.getItem('sentinal_theme') || 'dark',
  cameras: [],
  events: [],
  identities: [],
  zones: [],
  modules: [],
  weaponAlarm: null,
  toasts: [],
  wsConnected: false,
  gridLayout: '2x2',

  // Actions
  setGridLayout: (layout) => set({ gridLayout: layout }),
  dismissWeaponAlarm: () => set({ weaponAlarm: null }),
  addToast: (toast) => {
    const id = Date.now() + Math.random()
    set((state) => ({ toasts: [{ id, ...toast }, ...state.toasts].slice(0, 8) }))
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) }))
    }, toast.duration || 6000)
  },
  dismissToast: (id) => set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),

  setTheme: (theme) => {
    localStorage.setItem('sentinal_theme', theme)
    document.documentElement.setAttribute('data-theme', theme)
    set({ theme })
  },

  fetchModules: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/modules`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) set({ modules: await res.json() })
    } catch (_) {}
  },

  updateModule: async (moduleId, update) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/modules/${moduleId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(update),
      })
      if (res.ok) {
        get().fetchModules()
        return true
      }
    } catch (_) {}
    return false
  },

  login: async (username, password) => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ username, password }).toString(),
      })
      if (res.ok) {
        const data = await res.json()
        const token = data.access_token
        localStorage.setItem('sentinal_token', token)
        set({ token })
        return true
      }
    } catch (_) {}
    return false
  },

  logout: () => {
    localStorage.removeItem('sentinal_token')
    set({ token: null })
    get().stopWebSocket()
  },

  fetchCameras: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/cameras`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) set({ cameras: await res.json() })
    } catch (_) {}
  },

  fetchEvents: async (params = '') => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/events?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) return await res.json()
    } catch (_) {}
    return null
  },

  clearEvents: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/events`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      return res.ok
    } catch (_) { return false }
  },

  fetchIdentities: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/identities`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) set({ identities: await res.json() })
    } catch (_) {}
  },

  fetchZones: async (camId = '') => {
    try {
      const token = get().token
      const url = camId ? `${API_BASE}/api/zones?cam_id=${camId}` : `${API_BASE}/api/zones`
      const res = await fetch(url, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) {
        const data = await res.json()
        if (!camId) set({ zones: data })
        return data
      }
    } catch (_) {}
    return []
  },

  fetchStats: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/stats`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) return await res.json()
    } catch (_) {}
    return null
  },

  fetchAlertConfig: async () => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/alerts/config`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (res.ok) return await res.json()
    } catch (_) {}
    return null
  },

  addCamera: async (camera) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/cameras`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(camera),
      })
      return res
    } catch (_) { return { ok: false } }
  },

  deleteCamera: async (camId) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/cameras/${camId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      return res.ok
    } catch (_) { return false }
  },

  patchCamera: async (camId, patch) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/cameras/${camId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(patch),
      })
      if (res.ok) {
        get().fetchCameras()
        return true
      }
    } catch (_) {}
    return false
  },

  addZone: async (zone) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/zones`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(zone),
      })
      return res.ok
    } catch (_) { return false }
  },

  updateZone: async (zoneId, zone) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/zones/${zoneId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(zone),
      })
      return res.ok
    } catch (_) { return false }
  },

  deleteZone: async (zoneId) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/zones/${zoneId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      return res.ok
    } catch (_) { return false }
  },

  updateIdentity: async (globalId, name) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/identities/${globalId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ name }),
      })
      return res.ok
    } catch (_) { return false }
  },

  deleteIdentity: async (globalId) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/identities/${globalId}`, {
        method: 'DELETE',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      return res.ok
    } catch (_) { return false }
  },

  enrollFace: async (globalId, formData) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/identities/${globalId}/enroll`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      })
      return res.ok
    } catch (_) { return false }
  },

  updateAlertConfig: async (config) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/alerts/config`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(config),
      })
      return res.ok
    } catch (_) { return false }
  },

  testAlert: async (channel) => {
    try {
      const token = get().token
      const res = await fetch(`${API_BASE}/api/alerts/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ channel }),
      })
      return res.ok
    } catch (_) { return false }
  },

  startWebSocket: () => connectWebSocket(set, get),

  stopWebSocket: () => {
    clearTimeout(reconnectTimer)
    if (wsInstance) {
      wsInstance.onclose = null // Prevent reconnect logic
      if (wsInstance.readyState === WebSocket.CONNECTING || wsInstance.readyState === WebSocket.OPEN) {
        wsInstance.close()
      }
      wsInstance = null
    }
    set({ wsConnected: false })
  },
}))

export { API_BASE }
export default useStore
