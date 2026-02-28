import React, { useEffect, useState } from 'react';
import { fetchStats } from '../services/api';
import { Activity, Users, MapPin } from 'lucide-react';

const StatsPanel = () => {
    const [stats, setStats] = useState({ intrusions_24h: 0, unique_people_24h: 0, top_zone: "Loading..." });

    useEffect(() => {
        const loadStats = async () => {
            const data = await fetchStats();
            setStats(data);
        };
        loadStats();
        const interval = setInterval(loadStats, 10000); // refresh every 10s
        return () => clearInterval(interval);
    }, []);

    return (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
            <div className="card" style={{ flex: 1, padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', padding: '0.75rem', borderRadius: '8px' }}>
                    <Activity color="var(--danger)" size={24} />
                </div>
                <div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Intrusions (24h)</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{stats.intrusions_24h}</div>
                </div>
            </div>

            <div className="card" style={{ flex: 1, padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', padding: '0.75rem', borderRadius: '8px' }}>
                    <Users color="var(--accent)" size={24} />
                </div>
                <div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Unique People (24h)</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{stats.unique_people_24h}</div>
                </div>
            </div>

            <div className="card" style={{ flex: 1, padding: '1rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ backgroundColor: 'rgba(16, 185, 129, 0.1)', padding: '0.75rem', borderRadius: '8px' }}>
                    <MapPin color="var(--success)" size={24} />
                </div>
                <div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Top Zone</div>
                    <div style={{ fontSize: '1.2rem', fontWeight: 'bold', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '150px' }}>
                        {stats.top_zone || "None"}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default StatsPanel;
