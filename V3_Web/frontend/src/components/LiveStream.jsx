import React, { useState } from 'react';
import { getVideoStreamUrl } from '../services/api';
import { Camera, AlertCircle } from 'lucide-react';

const LiveStream = ({ cameraId, zones }) => {
    const streamUrl = getVideoStreamUrl(cameraId);
    const [hasError, setHasError] = useState(false);

    return (
        <div className="card">
            <div className="card-header">
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Camera size={18} />
                    <span>Live Feed: {cameraId}</span>
                </div>
            </div>

            <div className="card-body" style={{ padding: '1rem' }}>
                <div className="video-container">
                    <div className="video-status">
                        <span className={`status-dot ${hasError ? 'offline' : ''}`}></span>
                        {hasError ? 'Offline' : 'Live'}
                    </div>

                    {hasError ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem', color: 'var(--text-muted)' }}>
                            <AlertCircle size={48} />
                            <p>Stream unavailable or pipeline not running.</p>
                        </div>
                    ) : (
                        <img
                            src={streamUrl}
                            alt="Live Surveillance Feed"
                            onError={() => setHasError(true)}
                            crossOrigin="anonymous"
                        />
                    )}
                </div>

                {/* Helper info about zones */}
                <div style={{ marginTop: '1rem', display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Active Zones:</div>
                    {zones.map(z => (
                        <span key={z.id} style={{ fontSize: '0.875rem', backgroundColor: 'rgba(59, 130, 246, 0.2)', color: 'var(--accent)', padding: '0.1rem 0.5rem', borderRadius: '4px' }}>
                            {z.label}
                        </span>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default LiveStream;
