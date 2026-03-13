import { useState, useEffect, useCallback } from 'react'
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, AreaChart, Area } from 'recharts'
import { BarChart3, Activity, Camera, ShieldAlert, Zap, RefreshCw, Clock } from 'lucide-react'
import useStore from '../store/useStore'

export default function Analytics() {
  const fetchStatsStore = useStore((s) => s.fetchStats)
  const fetchEventsStore = useStore((s) => s.fetchEvents)
  
  const [stats, setStats] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const [statsData, eventsData] = await Promise.all([
        fetchStatsStore(),
        fetchEventsStore('limit=500'),
      ])

      if (statsData) setStats(statsData)
      if (eventsData) setEvents(eventsData)
    } catch (err) {
      console.error('Telemetry retrieval fault:', err)
    } finally {
      setLoading(false)
    }
  }, [fetchStatsStore, fetchEventsStore])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Group events by hour for line chart
  const eventsByHour = {}
  events.forEach((e) => {
    if (!e.timestamp) return
    const date = new Date(e.timestamp)
    const hour = date.getHours()
    const key = `${hour}:00`
    eventsByHour[key] = (eventsByHour[key] || 0) + 1
  })

  const hourlyData = Array.from({ length: 24 }, (_, i) => {
    const key = `${i}:00`
    return { hour: key, count: eventsByHour[key] || 0 }
  })

  const cameraData = Object.entries(events.reduce((acc, e) => {
    if (e.cam_id) acc[e.cam_id] = (acc[e.cam_id] || 0) + 1
    return acc
  }, {})).map(([camera, events]) => ({ camera, events }))

  const typeData = Object.entries(events.reduce((acc, e) => {
    if (e.alert_type) acc[e.alert_type] = (acc[e.alert_type] || 0) + 1
    return acc
  }, {})).map(([name, value]) => ({ name, value }))

  const COLORS = {
    intrusion: '#f59e0b',
    weapon: '#f43f5e',
    loitering: '#8b5cf6',
    crowding: '#d946ef',
    violence: '#ef4444',
    face_match: '#10b981',
    anomaly: '#3b82f6',
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={s.tooltip}>
          <p style={s.tooltipLabel}>{label}</p>
          <p style={s.tooltipValue}>{`${payload[0].value} EVENTS`}</p>
        </div>
      )
    }
    return null
  }

  if (loading && !stats) {
    return (
      <div style={s.root}>
        <div style={s.loadingBox}>
          <RefreshCw size={32} style={s.spin} />
          <p>SYNCHRONIZING TELEMETRY...</p>
        </div>
      </div>
    )
  }

  return (
    <div style={s.root}>
      <header style={s.header}>
        <div>
          <h2 style={s.title}>System Intelligence</h2>
          <p style={s.subtitle}>Deep analytics and behavioral patterns across the neural network</p>
        </div>
        <button style={s.syncBtn} onClick={fetchData}>
          <RefreshCw size={14} /> REFRESH DATA
        </button>
      </header>

      {/* Telemetry Cards */}
      <div style={s.cardsGrid}>
        <div style={s.telemetryCard}>
          <div style={s.cardIcon}><Zap size={20} color="var(--accent-primary)" /></div>
          <div style={s.cardData}>
            <div style={s.statValue}>{stats?.total_events || 0}</div>
            <div style={s.statLabel}>AGGREGATE EVENTS</div>
          </div>
        </div>
        <div style={s.telemetryCard}>
          <div style={s.cardIcon}><Activity size={20} color="var(--status-success)" /></div>
          <div style={s.cardData}>
            <div style={s.statValue}>{stats?.events_today || 0}</div>
            <div style={s.statLabel}>24H INTENSITY</div>
          </div>
        </div>
        <div style={s.telemetryCard}>
          <div style={s.cardIcon}><Camera size={20} color="var(--accent-secondary)" /></div>
          <div style={s.cardData}>
            <div style={s.statValue}>{stats?.active_cameras || 0}</div>
            <div style={s.statLabel}>ONLINE NODES</div>
          </div>
        </div>
        <div style={s.telemetryCard}>
          <div style={s.cardIcon}><ShieldAlert size={20} color="var(--status-danger)" /></div>
          <div style={s.cardData}>
            <div style={s.statValue}>{events.filter(e => e.alert_type === 'weapon').length}</div>
            <div style={s.statLabel}>CRITICAL THREATS</div>
          </div>
        </div>
      </div>

      {/* Analytics Terminal */}
      <div style={s.chartsContainer}>
        {/* Main Intensity Graph */}
        <div style={{ ...s.chartBox, gridColumn: 'span 2' }}>
          <div style={s.chartHeader}>
            <Clock size={14} />
            TEMPORAL INTENSITY (24H)
          </div>
          <div style={{ height: 300, marginTop: '20px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={hourlyData}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-base)" vertical={false} />
                <XAxis dataKey="hour" stroke="var(--text-dim)" fontSize={10} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-dim)" fontSize={10} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="count" stroke="var(--accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Node Distribution */}
        <div style={s.chartBox}>
          <div style={s.chartHeader}>
            <BarChart3 size={14} />
            NODE ALERT DISTRIBUTION
          </div>
          <div style={{ height: 300, marginTop: '20px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cameraData} layout="vertical">
                <CartesianGrid stroke="var(--border-base)" horizontal={false} strokeDasharray="3 3" />
                <XAxis type="number" stroke="var(--text-dim)" fontSize={10} hide />
                <YAxis dataKey="camera" type="category" stroke="var(--text-sub)" fontSize={10} width={80} tickLine={false} axisLine={false} />
                <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--border-base)' }} />
                <Bar dataKey="events" fill="var(--accent-secondary)" radius={[0, 4, 4, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Classification Mix */}
        <div style={s.chartBox}>
          <div style={s.chartHeader}>
            <Activity size={14} />
            THREAT CLASSIFICATION MIX
          </div>
          <div style={{ height: 300, marginTop: '20px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={typeData}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="var(--bg-surface)"
                  strokeWidth={2}
                >
                  {typeData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[entry.name] || 'var(--accent-primary)'} />
                  ))}
                </Pie>
                <Tooltip content={<CustomTooltip />} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '10px', paddingTop: '20px', color: 'var(--text-sub)' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  )
}

const s = {
  root: { display: 'flex', flexDirection: 'column', gap: '32px' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { margin: 0, fontSize: '1.75rem', fontWeight: 800, color: 'var(--text-main)', letterSpacing: '-0.02em' },
  subtitle: { margin: '6px 0 0', fontSize: '0.95rem', color: 'var(--text-sub)' },
  
  syncBtn: { 
    display: 'flex', alignItems: 'center', gap: '8px', 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    color: 'var(--text-main)', padding: '10px 16px', borderRadius: 'var(--radius-md)', 
    cursor: 'pointer', fontSize: '0.8rem', fontWeight: 700, transition: 'all 0.2s',
    boxShadow: 'var(--shadow-sm)'
  },

  cardsGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '24px' },
  telemetryCard: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '24px', display: 'flex', 
    alignItems: 'center', gap: '20px', boxShadow: 'var(--shadow-md)' 
  },
  cardIcon: { 
    width: '48px', height: '48px', borderRadius: 'var(--radius-md)', 
    background: 'var(--bg-surface-raised)', display: 'flex', 
    alignItems: 'center', justifyContent: 'center', border: '1px solid var(--border-bright)' 
  },
  statValue: { fontSize: '2rem', fontWeight: 900, color: 'var(--text-main)', lineHeight: '1', letterSpacing: '-0.03em' },
  statLabel: { fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-dim)', letterSpacing: '0.05em', marginTop: '6px' },

  chartsContainer: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' },
  chartBox: { 
    background: 'var(--bg-surface)', border: '1px solid var(--border-base)', 
    borderRadius: 'var(--radius-lg)', padding: '32px', boxShadow: 'var(--shadow-md)' 
  },
  chartHeader: { 
    display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem', 
    fontWeight: 800, color: 'var(--text-sub)', letterSpacing: '0.05em' 
  },

  tooltip: { background: 'var(--bg-surface)', border: '1px solid var(--border-bright)', padding: '12px 16px', borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-lg)' },
  tooltipLabel: { margin: 0, fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-dim)', textTransform: 'uppercase' },
  tooltipValue: { margin: '6px 0 0', fontSize: '1rem', fontWeight: 900, color: 'var(--text-main)' },

  loadingBox: { height: '400px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '16px', color: 'var(--text-dim)', letterSpacing: '2px', fontSize: '0.85rem', fontWeight: 600 },
  spin: { animation: 'spin 2s linear infinite' }
}
