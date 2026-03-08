import { create } from 'zustand'

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000/ws/live'

let wsInstance = null
let reconnectTimer = null
let reconnectDelay = 1000

function connectWebSocket(set, get) {
  if (wsInstance) return

  wsInstance = new WebSocket(WS_URL)

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
  cameras: [],
  events: [],
  identities: [],
  zones: [],
  weaponAlarm: null,
  wsConnected: false,
  gridLayout: '2x2',

  // Actions
  setGridLayout: (layout) => set({ gridLayout: layout }),
  dismissWeaponAlarm: () => set({ weaponAlarm: null }),

  fetchCameras: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/cameras`)
      if (res.ok) set({ cameras: await res.json() })
    } catch (_) {}
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
