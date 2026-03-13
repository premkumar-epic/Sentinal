import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldCheck, Lock, User, AlertCircle } from 'lucide-react';
import useStore from '../store/useStore';

const Login = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  
  const navigate = useNavigate();
  const login = useStore((state) => state.login);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsAuthenticating(true);

    const success = await login(username, password);
    
    setIsAuthenticating(false);
    if (success) {
      navigate('/');
    } else {
      setError('Invalid system credentials');
    }
  };

  const s = {
    container: {
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      width: '100%',
      backgroundColor: 'var(--bg-app)',
      color: 'var(--text-main)',
      margin: 0,
      padding: '20px',
      position: 'relative',
      overflow: 'hidden'
    },
    bgAccent: {
      position: 'absolute',
      width: '600px',
      height: '600px',
      background: 'var(--accent-primary)',
      opacity: 0.05,
      filter: 'blur(100px)',
      borderRadius: '50%',
      top: '50%',
      left: '50%',
      transform: 'translate(-50%, -50%)',
      pointerEvents: 'none',
      zIndex: 0
    },
    card: {
      display: 'flex',
      flexDirection: 'column',
      width: '100%',
      maxWidth: '420px',
      padding: '48px',
      backgroundColor: 'var(--bg-surface)',
      border: '1px solid var(--border-bright)',
      borderRadius: 'var(--radius-lg)',
      boxShadow: 'var(--shadow-lg)',
      zIndex: 1,
    },
    header: {
      textAlign: 'center',
      marginBottom: '40px',
    },
    logoIcon: {
      width: '56px',
      height: '56px',
      background: 'var(--accent-primary)',
      borderRadius: '16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      margin: '0 auto 24px',
      color: '#fff',
      boxShadow: '0 8px 24px var(--accent-soft)',
    },
    title: {
      fontSize: '1.75rem',
      fontWeight: 800,
      letterSpacing: '-0.03em',
      margin: '0 0 8px 0',
      color: 'var(--text-main)',
    },
    subtitle: {
      color: 'var(--text-sub)',
      fontSize: '0.9rem',
      fontWeight: 500,
      margin: 0,
    },
    inputGroup: {
      display: 'flex',
      flexDirection: 'column',
      marginBottom: '24px',
      position: 'relative',
    },
    label: {
      marginBottom: '8px',
      color: 'var(--text-main)',
      fontSize: '0.8rem',
      fontWeight: 600,
    },
    inputWrapper: {
      position: 'relative',
      display: 'flex',
      alignItems: 'center',
    },
    inputIcon: {
      position: 'absolute',
      left: '14px',
      color: 'var(--text-dim)',
    },
    input: {
      width: '100%',
      backgroundColor: 'var(--bg-app)',
      border: '1px solid var(--border-base)',
      borderRadius: 'var(--radius-md)',
      color: 'var(--text-main)',
      padding: '14px 14px 14px 44px',
      fontSize: '0.95rem',
      outline: 'none',
      transition: 'all 0.2s ease',
    },
    button: {
      background: isAuthenticating 
        ? 'var(--bg-surface-raised)' 
        : 'var(--accent-primary)',
      color: isAuthenticating ? 'var(--text-sub)' : '#ffffff',
      border: 'none',
      borderRadius: 'var(--radius-md)',
      padding: '16px',
      fontSize: '0.95rem',
      fontWeight: 600,
      cursor: isAuthenticating ? 'not-allowed' : 'pointer',
      marginTop: '8px',
      transition: 'all 0.2s ease',
      boxShadow: isAuthenticating ? 'none' : '0 4px 12px var(--accent-soft)',
    },
    error: {
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      backgroundColor: 'rgba(225, 29, 72, 0.05)',
      border: '1px solid rgba(225, 29, 72, 0.2)',
      color: 'var(--status-danger)',
      padding: '14px',
      borderRadius: 'var(--radius-md)',
      fontSize: '0.85rem',
      fontWeight: 500,
      marginTop: '24px',
    }
  };

  return (
    <div style={s.container}>
      <div style={s.bgAccent} />
      <div style={s.card}>
        <div style={s.header}>
          <div style={s.logoIcon}>
            <ShieldCheck size={28} />
          </div>
          <h1 style={s.title}>SENTINAL v2</h1>
          <p style={s.subtitle}>Secure AI Command Interface</p>
        </div>
        
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={s.inputGroup}>
            <label style={s.label}>Username</label>
            <div style={s.inputWrapper}>
              <User size={18} style={s.inputIcon} />
              <input
                style={s.input}
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={isAuthenticating}
                placeholder="system_admin"
                required
                autoFocus
              />
            </div>
          </div>
          
          <div style={s.inputGroup}>
            <label style={s.label}>Password</label>
            <div style={s.inputWrapper}>
              <Lock size={18} style={s.inputIcon} />
              <input
                style={s.input}
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isAuthenticating}
                placeholder="••••••••"
                required
              />
            </div>
          </div>
          
          <button 
            style={s.button} 
            type="submit" 
            disabled={isAuthenticating}
          >
            {isAuthenticating ? 'Authorizing Access...' : 'SECURE LOGIN'}
          </button>
          
          {error && (
            <div style={s.error}>
              <AlertCircle size={16} />
              {error}
            </div>
          )}
        </form>
      </div>
      
      <div style={{ marginTop: '32px', color: 'var(--text-dim)', fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
        &copy; 2026 Sentinal Surveillance Systems
      </div>
    </div>
  );
};

export default Login;
