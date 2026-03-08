import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import LiveView from './pages/LiveView'
import Events from './pages/Events'
import Cameras from './pages/Cameras'
import Identities from './pages/Identities'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Zones from './pages/Zones'
import AlertBanner from './components/AlertBanner'

const navStyle = ({ isActive }) => ({
  color: isActive ? '#00e5ff' : '#aaa',
  textDecoration: 'none',
  fontFamily: 'monospace',
  fontSize: '0.85rem',
  padding: '4px 10px',
  borderBottom: isActive ? '2px solid #00e5ff' : '2px solid transparent',
})

export default function App() {
  return (
    <BrowserRouter>
      <AlertBanner />
      <nav style={{ background: '#111', borderBottom: '1px solid #333', display: 'flex', gap: '4px', padding: '0 12px' }}>
        <NavLink to="/" end style={navStyle}>Live View</NavLink>
        <NavLink to="/cameras" style={navStyle}>Cameras</NavLink>
        <NavLink to="/events" style={navStyle}>Events</NavLink>
        <NavLink to="/identities" style={navStyle}>Identities</NavLink>
        <NavLink to="/alerts" style={navStyle}>Alerts</NavLink>
        <NavLink to="/analytics" style={navStyle}>Analytics</NavLink>
        <NavLink to="/zones" style={navStyle}>Zones</NavLink>
      </nav>
      <Routes>
        <Route path="/" element={<LiveView />} />
        <Route path="/cameras" element={<Cameras />} />
        <Route path="/events" element={<Events />} />
        <Route path="/identities" element={<Identities />} />
        <Route path="/alerts" element={<Alerts />} />
        <Route path="/analytics" element={<Analytics />} />
        <Route path="/zones" element={<Zones />} />
      </Routes>
    </BrowserRouter>
  )
}
