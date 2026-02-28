import React, { useState, useEffect } from 'react';
import LiveStream from '../components/LiveStream';
import EventLog from '../components/EventLog';
import { fetchZones } from '../services/api';

const Dashboard = () => {
    const [zones, setZones] = useState([]);

    // Basic active camera ID assumption for the MVP
    const cameraId = "cam_01";

    useEffect(() => {
        const loadZones = async () => {
            const data = await fetchZones();
            setZones(data);
        };
        loadZones();
    }, []);

    return (
        <div className="dashboard-layout">
            <div className="main-panel">
                <LiveStream cameraId={cameraId} zones={zones} />
            </div>

            <div className="side-panel">
                <EventLog />
            </div>
        </div>
    );
};

export default Dashboard;
