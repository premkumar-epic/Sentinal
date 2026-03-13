import React from 'react';
import { User, ShieldCheck } from 'lucide-react';

const PersonBadge = ({ name, globalId, enrolled }) => {
  const s = {
    badge: {
      display: 'inline-flex',
      alignItems: 'center',
      gap: '6px',
      padding: '4px 10px',
      background: enrolled ? 'rgba(16, 185, 129, 0.1)' : 'var(--glass-bg)',
      border: `1px solid ${enrolled ? 'rgba(16, 185, 129, 0.3)' : 'var(--glass-border)'}`,
      borderRadius: 'var(--radius-sm)',
      color: enrolled ? 'var(--status-success)' : 'var(--text-primary)',
      fontSize: '0.7rem',
      fontWeight: 700,
      letterSpacing: '0.5px',
      transition: 'all 0.2s',
    },
    icon: {
      flexShrink: 0,
    },
    label: {
      maxWidth: '120px',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap',
    }
  };

  return (
    <div style={s.badge}>
      {enrolled ? <ShieldCheck size={12} style={s.icon} /> : <User size={12} style={s.icon} />}
      <span style={s.label}>{name || `SUBJECT_${globalId?.slice(0, 6).toUpperCase()}`}</span>
    </div>
  );
};

export default PersonBadge;
