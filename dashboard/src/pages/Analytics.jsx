import { useState, useEffect } from 'react'
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { API_BASE } from '../store/useStore'

export default function Analytics() {
  const [stats, setStats] = useState(null)
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [statsRes, eventsRes] = await Promise.all([
        fetch(`${API_BASE}/api/stats`),
        fetch(`${API_BASE}/api/events?limit=500`),
      ])

      if (statsRes.ok) {
        setStats(await statsRes.json())
      }

      if (eventsRes.ok) {
        setEvents(await eventsRes.json())
      }
    } catch (err) {
      console.error('Failed to fetch analytics:', err)
    } finally {
      setLoading(false)
    }
  }

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

  // Group events by camera for bar chart
  const eventsByCam = {}
  events.forEach((e) => {
    if (!e.cam_id) return
    eventsByCam[e.cam_id] = (eventsByCam[e.cam_id] || 0) + 1
  })

  const cameraData = Object.entries(eventsByCam).map(([cam, count]) => ({
    camera: cam,
    events: count,
  }))

  // Group events by type for pie chart
  const eventsByType = {}
  events.forEach((e) => {
    if (!e.alert_type) return
    eventsByType[e.alert_type] = (eventsByType[e.alert_type] || 0) + 1
  })

  const typeData = Object.entries(eventsByType).map(([type, count]) => ({
    name: type,
    value: count,
  }))

  const COLORS = {
    intrusion: '#ff9100',
    weapon: '#ff1744',
    loitering: '#ffea00',
    crowding: '#e040fb',
    violence: '#ff1744',
    face_match: '#00e676',
    anomaly: '#00bfff',
  }

  if (loading) {
    return (
      <div style={s.root}>
        <p style={s.dim}>Loading analytics...</p>
      </div>
    )
  }

  return (
    <div style={s.root}>
      <h2 style={s.title}>Analytics & Statistics</h2>

      {/* Summary Cards */}
      <div style={s.cardsGrid}>
        <div style={s.card}>
          <div style={s.cardLabel}>Total Events</div>
          <div style={s.cardValue}>{stats?.total_events || 0}</div>
        </div>
        <div style={s.card}>
          <div style={s.cardLabel}>Events Today</div>
          <div style={s.cardValue}>{stats?.events_today || 0}</div>
        </div>
        <div style={s.card}>
          <div style={s.cardLabel}>Active Cameras</div>
          <div style={s.cardValue}>{stats?.active_cameras || 0}</div>
        </div>
      </div>

      {/* Charts */}
      <div style={s.chartsContainer}>
        {/* Line Chart - Events by Hour */}
        <div style={s.chartBox}>
          <h3 style={s.chartTitle}>Events by Hour (Last 24 Hours)</h3>
          {hourlyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={hourlyData}>
                <CartesianGrid stroke="#333" />
                <XAxis dataKey="hour" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #444', color: '#e0e0e0' }}
                  cursor={{ stroke: '#00e5ff', strokeWidth: 2 }}
                />
                <Line type="monotone" dataKey="count" stroke="#00e5ff" dot={{ fill: '#00e5ff' }} />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <p style={s.dim}>No data</p>
          )}
        </div>

        {/* Bar Chart - Events by Camera */}
        <div style={s.chartBox}>
          <h3 style={s.chartTitle}>Events by Camera</h3>
          {cameraData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={cameraData}>
                <CartesianGrid stroke="#333" />
                <XAxis dataKey="camera" stroke="#888" />
                <YAxis stroke="#888" />
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #444', color: '#e0e0e0' }}
                />
                <Bar dataKey="events" fill="#00e5ff" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p style={s.dim}>No data</p>
          )}
        </div>

        {/* Pie Chart - Events by Type */}
        <div style={s.chartBox}>
          <h3 style={s.chartTitle}>Events by Type</h3>
          {typeData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={typeData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {typeData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={COLORS[entry.name] || '#00e5ff'}
                    />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1a1a1a', border: '1px solid #444', color: '#e0e0e0' }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p style={s.dim}>No data</p>
          )}
        </div>
      </div>

      {/* Refresh Button */}
      <div style={s.actions}>
        <button style={s.btn} onClick={fetchData}>
          Refresh
        </button>
      </div>
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
  cardsGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
    gap: '12px',
    marginBottom: '24px',
  },
  card: {
    background: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '6px',
    padding: '16px',
    textAlign: 'center',
  },
  cardLabel: {
    color: '#777',
    fontSize: '0.85rem',
    marginBottom: '8px',
  },
  cardValue: {
    color: '#00e5ff',
    fontSize: '2rem',
    fontWeight: 'bold',
  },
  chartsContainer: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: '20px',
    marginBottom: '20px',
  },
  chartBox: {
    background: '#1a1a1a',
    border: '1px solid #333',
    borderRadius: '6px',
    padding: '16px',
  },
  chartTitle: {
    margin: '0 0 12px',
    color: '#00e5ff',
    fontSize: '0.95rem',
  },
  dim: {
    color: '#555',
    fontSize: '0.85rem',
  },
  actions: {
    display: 'flex',
    gap: '12px',
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
}
