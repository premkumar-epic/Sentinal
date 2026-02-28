import React, { useState, useEffect } from 'react';
import { fetchEvents } from '../services/api';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { ShieldAlert, Image as ImageIcon } from 'lucide-react';

const EventLog = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);

    // Poll for new events every 2 seconds
    useEffect(() => {
        const loadEvents = async () => {
            const data = await fetchEvents(50);
            setEvents(data);
            setLoading(false);
        };

        loadEvents();
        const interval = setInterval(loadEvents, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="card" style={{ height: '100%' }}>
            <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldAlert size={18} color="var(--danger)" />
                    <span>Intrusion Alert Log</span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Live Updates
                </span>
            </div>

            <div className="card-body" style={{ padding: '1rem', overflowY: 'auto' }}>
                {loading ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        Loading events...
                    </div>
                ) : events.length === 0 ? (
                    <div style={{ display: 'flex', justifyContent: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                        No intrusions detected.
                    </div>
                ) : (
                    <div className="event-list">
                        {events.map((evt) => (
                            <div key={evt.id} className="event-item">
                                <div className="event-icon">
                                    <ShieldAlert size={20} />
                                </div>
                                <div className="event-content">
                                    <div className="event-header">
                                        <div className="event-title">Intrusion: {evt.zone}</div>
                                        <div className="event-time">
                                            {formatDistanceToNow(parseISO(evt.timestamp), { addSuffix: true })}
                                        </div>
                                    </div>
                                    <div className="event-details">
                                        Track ID: {evt.object_id} &bull; Camera: {evt.camera_id}
                                    </div>
                                    {evt.snapshot_path && (
                                        <div style={{ marginTop: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--accent)', cursor: 'pointer' }}>
                                            <ImageIcon size={14} /> View Snapshot
                                        </div>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default EventLog;
