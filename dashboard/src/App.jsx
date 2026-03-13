import { BrowserRouter, Routes, Route, NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { 
  LayoutDashboard, 
  Video, 
  History, 
  Users, 
  Bell, 
  BarChart3, 
  ShieldAlert,
  Cpu,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon
} from 'lucide-react'
import { useState, useEffect } from 'react'

import LiveView from './pages/LiveView'
import Events from './pages/Events'
import Cameras from './pages/Cameras'
import Identities from './pages/Identities'
import Alerts from './pages/Alerts'
import Analytics from './pages/Analytics'
import Zones from './pages/Zones'
import Modules from './pages/Modules'
import Login from './pages/Login'
import AlertBanner from './components/AlertBanner'
import ToastStack from './components/ToastStack'
import useStore from './store/useStore'

const SidebarItem = ({ to, icon: Icon, label, collapsed }) => (
  <NavLink 
    to={to} 
    end={to === '/'}
    style={({ isActive }) => ({
      display: 'flex',
      alignItems: 'center',
      padding: '12px 16px',
      margin: '2px 12px',
      borderRadius: 'var(--radius-md)',
      textDecoration: 'none',
      color: isActive ? 'var(--text-main)' : 'var(--text-sub)',
      background: isActive ? 'var(--glass-bg)' : 'transparent',
      border: '1px solid',
      borderColor: isActive ? 'var(--border-bright)' : 'transparent',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      gap: '12px',
      position: 'relative',
      overflow: 'hidden',
      transform: 'translateZ(0)',
    })}
    className={({ isActive }) => isActive ? 'sidebar-item-active' : 'sidebar-item'}
  >
    <Icon size={18} style={{ 
      flexShrink: 0,
      color: 'inherit',
      transition: 'transform 0.3s ease'
    }} />
    {!collapsed && <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{label}</span>}
    {/* Active Glow Indicator */}
    <div style={{
      position: 'absolute',
      left: 0,
      width: '3px',
      height: '50%',
      background: 'var(--accent-primary)',
      borderRadius: '0 4px 4px 0',
      boxShadow: '0 0 10px var(--accent-primary)',
      opacity: 0, 
      transition: 'opacity 0.3s'
    }} className="active-glow" />
  </NavLink>
)

const Sidebar = ({ collapsed, setCollapsed }) => {
  const logout = useStore((s) => s.logout)
  const theme = useStore((s) => s.theme)
  const setTheme = useStore((s) => s.setTheme)
  const wsConnected = useStore((s) => s.wsConnected)
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  return (
    <aside style={{
      width: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
      height: '100vh',
      background: 'var(--bg-sidebar)',
      borderRight: '1px solid var(--border-base)',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
      position: 'fixed',
      left: 0,
      top: 0,
      zIndex: 100,
      boxShadow: 'var(--shadow-md)'
    }}>
      {/* Brand */}
      <div style={{ 
        padding: collapsed ? '32px 0' : '32px 24px', 
        display: 'flex', 
        alignItems: 'center', 
        justifyContent: collapsed ? 'center' : 'flex-start',
        gap: '14px',
        marginBottom: '12px'
      }}>
        <div style={{ 
          width: '36px', 
          height: '36px', 
          background: wsConnected ? 'var(--accent-primary)' : 'var(--status-danger)',
          borderRadius: '10px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          boxShadow: wsConnected ? '0 4px 12px var(--accent-soft)' : '0 4px 12px rgba(225, 29, 72, 0.3)',
          flexShrink: 0,
          transition: 'all 0.3s'
        }}>
          <ShieldAlert size={22} />
        </div>
        {!collapsed && (
          <div style={{ transition: 'opacity 0.3s', whiteSpace: 'nowrap' }}>
            <div style={{ fontWeight: 800, fontSize: '1.2rem', letterSpacing: '-0.02em', lineHeight: 1.1, color: 'var(--text-main)' }}>SENTINAL</div>
            <div style={{ 
              fontSize: '0.65rem', 
              color: wsConnected ? 'var(--status-success)' : 'var(--status-danger)', 
              display: 'flex', 
              alignItems: 'center', 
              gap: '5px', 
              marginTop: '4px', 
              fontWeight: 700, 
              letterSpacing: '0.05em',
              transition: 'color 0.3s'
            }}>
              <span style={{ 
                width: '6px', 
                height: '6px', 
                background: 'currentColor', 
                borderRadius: '50%', 
                boxShadow: `0 0 6px ${wsConnected ? 'var(--status-success)' : 'var(--status-danger)'}`,
                transition: 'all 0.3s'
              }} />
              {wsConnected ? 'SYSTEM ONLINE' : 'SYSTEM OFFLINE'}
            </div>
          </div>
        )}
      </div>

      {/* Nav Items */}
      <nav style={{ flex: 1, overflowY: 'auto' }}>
        <SidebarItem to="/" icon={LayoutDashboard} label="Live View" collapsed={collapsed} />
        <SidebarItem to="/cameras" icon={Video} label="Cameras" collapsed={collapsed} />
        <SidebarItem to="/zones" icon={ShieldAlert} label="Zones" collapsed={collapsed} />
        <SidebarItem to="/events" icon={History} label="Event Log" collapsed={collapsed} />
        <SidebarItem to="/identities" icon={Users} label="Identities" collapsed={collapsed} />
        <SidebarItem to="/analytics" icon={BarChart3} label="Analytics" collapsed={collapsed} />
        <SidebarItem to="/modules" icon={Cpu} label="Detection Modules" collapsed={collapsed} />
        <SidebarItem to="/alerts" icon={Bell} label="Alert Config" collapsed={collapsed} />
      </nav>

      {/* Footer */}
      <div style={{ padding: '16px 0', borderTop: '1px solid var(--border-base)' }}>
        <div style={{ 
          display: 'flex', 
          flexDirection: collapsed ? 'column' : 'row',
          padding: '0 12px', 
          gap: '8px', 
          marginBottom: '12px',
          alignItems: 'center'
        }}>
          <button 
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
            style={{
              width: collapsed ? '40px' : 'auto',
              flex: collapsed ? 'none' : 0,
              background: 'transparent',
              border: '1px solid transparent',
              color: 'var(--text-sub)',
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-surface-raised)'}
            onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <button 
            onClick={() => setCollapsed(!collapsed)}
            style={{
              width: collapsed ? '40px' : 'auto',
              flex: collapsed ? 'none' : 1,
              background: 'transparent',
              border: '1px solid var(--border-base)',
              color: 'var(--text-sub)',
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              cursor: 'pointer',
              fontSize: '0.85rem',
              fontWeight: 500,
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => e.currentTarget.style.background = 'var(--bg-surface-raised)'}
            onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
          >
            {collapsed ? <ChevronRight size={18} /> : <><ChevronLeft size={18} /> Collapse</>}
          </button>
        </div>
        
        <button 
          onClick={handleLogout}
          style={{
            width: 'calc(100% - 24px)',
            margin: '0 12px 12px',
            background: 'var(--bg-app)',
            border: '1px solid var(--border-bright)',
            color: 'var(--text-main)',
            padding: '10px',
            borderRadius: 'var(--radius-md)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '12px',
            cursor: 'pointer',
            fontSize: '0.875rem',
            fontWeight: 600,
            transition: 'all 0.2s'
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.background = 'rgba(225, 29, 72, 0.1)';
            e.currentTarget.style.color = 'var(--status-danger)';
            e.currentTarget.style.borderColor = 'rgba(225, 29, 72, 0.2)';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.background = 'var(--bg-app)';
            e.currentTarget.style.color = 'var(--text-main)';
            e.currentTarget.style.borderColor = 'var(--border-bright)';
          }}
        >
          <LogOut size={18} />
          {!collapsed && 'Sign Out'}
        </button>
      </div>
    </aside>
  )
}

const ProtectedRoute = () => {
  const token = useStore((state) => state.token)
  const [collapsed, setCollapsed] = useState(false)

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg-app)' }}>
      <Sidebar collapsed={collapsed} setCollapsed={setCollapsed} />
      <main style={{ 
        flex: 1, 
        marginLeft: collapsed ? 'var(--sidebar-collapsed)' : 'var(--sidebar-width)',
        transition: 'margin-left 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        padding: '32px',
        maxWidth: '1600px',
        marginRight: 'auto',
        minWidth: 0
      }}>
        <AlertBanner />
        <ToastStack />
        <div className="page-transition">
          <Outlet />
        </div>
      </main>
    </div>
  )
}

export default function App() {
  const token = useStore((s) => s.token)
  const startWebSocket = useStore((s) => s.startWebSocket)
  const stopWebSocket = useStore((s) => s.stopWebSocket)

  useEffect(() => {
    if (token) {
      startWebSocket()
    } else {
      stopWebSocket()
    }
  }, [token])

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<LiveView />} />
          <Route path="/cameras" element={<Cameras />} />
          <Route path="/events" element={<Events />} />
          <Route path="/identities" element={<Identities />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/modules" element={<Modules />} />
          <Route path="/zones" element={<Zones />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
