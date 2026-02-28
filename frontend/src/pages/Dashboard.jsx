import React, { useState, useEffect } from 'react';
import LiveStream from '../components/LiveStream';
import EventLog from '../components/EventLog';
import StatsPanel from '../components/StatsPanel';
import ZoneEditor from '../components/ZoneEditor';
import { fetchZones, fetchCameras, startCamera } from '../services/api';
import { Settings, Play } from 'lucide-react';

const Dashboard = () => {
    const [zones, setZones] = useState([]);
    const [cameras, setCameras] = useState([]);
    const [activeCameraId, setActiveCameraId] = useState("cam_01");
    const [isEditorOpen, setIsEditorOpen] = useState(false);
    const [starting, setStarting] = useState(false);

    const loadCoreData = async () => {
        const [zData, cData] = await Promise.all([fetchZones(), fetchCameras()]);
        setZones(zData);
        setCameras(cData);
    };

    useEffect(() => {
        loadCoreData();
        const interval = setInterval(() => fetchCameras().then(setCameras), 5000);
        return () => clearInterval(interval);
    }, []);

    const handleEditorSave = (newZones) => {
        setZones(newZones);
        setIsEditorOpen(false);
    };

    const handleStartCamera = async () => {
        setStarting(true);
        try {
            await startCamera(activeCameraId);
            await new Promise(r => setTimeout(r, 1000));
            await loadCoreData();
        } finally {
            setStarting(false);
        }
    };

    const isRunning = cameras.some(c => c.id === activeCameraId);

    return (
        <div className="dashboard-layout">
            <div className="main-panel">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                    <h2 style={{ margin: 0 }}>Surveillance Feed</h2>
                    
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                        <select 
                            value={activeCameraId} 
                            onChange={(e) => setActiveCameraId(e.target.value)}
                            style={{ padding: '0.5rem', borderRadius: '4px', backgroundColor: '#1a1a1a', color: '#fff', border: '1px solid #333' }}
                        >
                            <option value="cam_01">Camera 1 (cam_01)</option>
                            <option value="cam_02">Camera 2 (cam_02)</option>
                        </select>

                        {!isRunning && (
                            <button 
                                className="primary-button" 
                                style={{ backgroundColor: 'var(--success)' }}
                                onClick={handleStartCamera}
                                disabled={starting}
                            >
                                <Play size={16} /> {starting ? "Starting..." : "Start Headless Pipeline"}
                            </button>
                        )}
                        
                        <button className="secondary-button" onClick={() => setIsEditorOpen(true)}>
                            <Settings size={16} /> Edit Zones
                        </button>
                    </div>
                </div>

                <StatsPanel />
                <LiveStream cameraId={activeCameraId} zones={zones} />
            </div>

            <div className="side-panel">
                <EventLog />
            </div>

            {isEditorOpen && (
                <ZoneEditor 
                    cameraId={activeCameraId}
                    existingZones={zones} 
                    onClose={() => setIsEditorOpen(false)} 
                    onSaveComplete={handleEditorSave}
                />
            )}
        </div>
    );
};

export default Dashboard;
