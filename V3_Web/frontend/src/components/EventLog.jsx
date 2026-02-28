import React, { useState, useEffect, useRef } from 'react';
import { fetchEvents } from '../services/api';
import { formatDistanceToNow, parseISO } from 'date-fns';
import { ShieldAlert, Image as ImageIcon } from 'lucide-react';

const WS_URL = 'ws://localhost:8000/ws/events';
const SNAPSHOT_BASE = 'http://localhost:8000/snapshots';

const EventLog = () => {
    const [events, setEvents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [wsConnected, setWsConnected] = useState(false);
    const wsRef = useRef(null);

    // Initial load via REST
    useEffect(() => {
        fetchEvents(50).then(data => {
            setEvents(data);
            setLoading(false);
        });
    }, []);

    // Real-time updates via WebSocket; fall back to polling if WS unavailable
    useEffect(() => {
        let fallbackInterval = null;

        const connect = () => {
            try {
                const ws = new WebSocket(WS_URL);
                wsRef.current = ws;

                ws.onopen = () => setWsConnected(true);

                ws.onmessage = (e) => {
                    const data = JSON.parse(e.data);
                    if (data.type === 'ping') return;
                    setEvents(prev => [data, ...prev].slice(0, 100));
                };

                ws.onclose = () => {
                    setWsConnected(false);
                    // Fall back to polling every 2s if WebSocket drops
                    fallbackInterval = setInterval(() => {
                        fetchEvents(50).then(setEvents);
                    }, 2000);
                };

                ws.onerror = () => ws.close();
            } catch {
                // WebSocket not available at all — use polling
                fallbackInterval = setInterval(() => {
                    fetchEvents(50).then(setEvents);
                }, 2000);
            }
        };

        connect();
        return () => {
            wsRef.current?.close();
            clearInterval(fallbackInterval);
        };
    }, []);

    const getSnapshotFilename = (path) => {
        if (!path) return null;
        return path.replace(/\\/g, '/').split('/').pop();
    };

    return (
        <div className="card" style={{ height: '100%' }}>
            <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <ShieldAlert size={18} color="var(--danger)" />
                    <span>Intrusion Alert Log</span>
                </div>
                <span style={{ fontSize: '0.75rem', color: wsConnected ? 'var(--accent)' : 'var(--text-muted)' }}>
                    {wsConnected ? '⬤ Live' : 'Polling'}
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
                        {events.map((evt) => {
                            const snapshotFile = getSnapshotFilename(evt.snapshot_path);
                            return (
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
                                        {snapshotFile && (
                                            <a
                                                href={`${SNAPSHOT_BASE}/${snapshotFile}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                style={{ marginTop: '0.5rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--accent)', textDecoration: 'none' }}
                                            >
                                                <ImageIcon size={14} /> View Snapshot
                                            </a>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>
        </div>
    );
};

export default EventLog;
