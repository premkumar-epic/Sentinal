import React, { useState, useRef, useEffect } from 'react';
import { updateZones, getVideoStreamUrl } from '../services/api';
import { Save, Trash2, Edit3, X } from 'lucide-react';

const ZoneEditor = ({ cameraId, existingZones, onClose, onSaveComplete }) => {
    // Canvas coordinate system matches Stream resolution (assume 640x360 default)
    const CANVAS_WIDTH = 640;
    const CANVAS_HEIGHT = 360;

    const [zones, setZones] = useState(existingZones || []);
    const [currentPolygon, setCurrentPolygon] = useState([]);
    const [isDrawing, setIsDrawing] = useState(false);
    const canvasRef = useRef(null);

    const streamUrl = getVideoStreamUrl(cameraId);

    const drawCanvas = () => {
        const ctx = canvasRef.current?.getContext('2d');
        if (!ctx) return;
        ctx.clearRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

        // Draw existing zones
        zones.forEach((z) => {
            if (z.polygon.length === 0) return;
            ctx.beginPath();
            ctx.moveTo(z.polygon[0][0], z.polygon[0][1]);
            z.polygon.forEach(p => ctx.lineTo(p[0], p[1]));
            ctx.closePath();
            ctx.fillStyle = 'rgba(0, 255, 255, 0.2)';
            ctx.fill();
            ctx.strokeStyle = '#00FFFF';
            ctx.lineWidth = 2;
            ctx.stroke();

            ctx.fillStyle = '#00FFFF';
            ctx.font = '14px sans-serif';
            ctx.fillText(z.label, z.polygon[0][0], z.polygon[0][1] - 5);
        });

        // Draw current polygon
        if (currentPolygon.length > 0) {
            ctx.beginPath();
            ctx.moveTo(currentPolygon[0][0], currentPolygon[0][1]);
            currentPolygon.forEach(p => ctx.lineTo(p[0], p[1]));
            if (!isDrawing && currentPolygon.length > 2) ctx.closePath();
            
            ctx.fillStyle = 'rgba(255, 0, 0, 0.3)';
            if (!isDrawing && currentPolygon.length > 2) ctx.fill();
            
            ctx.strokeStyle = '#FF0000';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Draw points
            currentPolygon.forEach(p => {
                ctx.beginPath();
                ctx.arc(p[0], p[1], 4, 0, Math.PI * 2);
                ctx.fillStyle = '#FFFFFF';
                ctx.fill();
                ctx.stroke();
            });
        }
    };

    useEffect(() => {
        drawCanvas();
    }, [zones, currentPolygon, isDrawing]);

    const handleCanvasClick = (e) => {
        if (!isDrawing) return;
        const rect = canvasRef.current.getBoundingClientRect();
        
        // Scale coordinates from CSS size to internal canvas size
        const scaleX = CANVAS_WIDTH / rect.width;
        const scaleY = CANVAS_HEIGHT / rect.height;
        
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;
        
        setCurrentPolygon([...currentPolygon, [Math.round(x), Math.round(y)]]);
    };

    const finishDrawing = () => {
        if (currentPolygon.length < 3) {
            alert("A zone needs at least 3 points");
            return;
        }
        const label = prompt("Enter a name for this zone:", `Zone ${zones.length + 1}`);
        if (label) {
            const newZone = {
                id: `zone_${Date.now()}`,
                label: label,
                polygon: currentPolygon
            };
            setZones([...zones, newZone]);
        }
        setCurrentPolygon([]);
        setIsDrawing(false);
    };

    const clearAll = () => {
        if(window.confirm("Are you sure you want to delete all zones?")) {
            setZones([]);
            setCurrentPolygon([]);
        }
    };

    const handleSave = async () => {
        try {
            await updateZones(zones);
            onSaveComplete(zones);
        } catch (err) {
            alert("Failed to save zones");
        }
    };

    return (
        <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.8)', zIndex: 1000,
            display: 'flex', justifyContent: 'center', alignItems: 'center'
        }}>
            <div className="card" style={{ width: '800px', maxWidth: '95vw', padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                    <h3 style={{ margin: 0, color: '#fff' }}>Zone Editor</h3>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer' }}><X /></button>
                </div>

                <div style={{ position: 'relative', width: '100%', aspectRatio: '16/9', backgroundColor: '#000', marginBottom: '1rem', overflow: 'hidden', borderRadius: '8px' }}>
                    {/* Background live stream */}
                    <img 
                        src={streamUrl} 
                        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain', opacity: 0.5 }} 
                        alt="background stream"
                        crossOrigin="anonymous"
                    />
                    {/* Drawing canvas overlay */}
                    <canvas
                        ref={canvasRef}
                        width={CANVAS_WIDTH}
                        height={CANVAS_HEIGHT}
                        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', cursor: isDrawing ? 'crosshair' : 'default' }}
                        onClick={handleCanvasClick}
                    />
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {!isDrawing ? (
                            <button className="primary-button" onClick={() => setIsDrawing(true)}>
                                <Edit3 size={16} /> Draw New Zone
                            </button>
                        ) : (
                            <button className="primary-button" style={{ backgroundColor: 'var(--success)' }} onClick={finishDrawing}>
                                Finish Polygon
                            </button>
                        )}
                        <button className="secondary-button" onClick={clearAll} style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>
                            <Trash2 size={16} /> Clear All
                        </button>
                    </div>

                    <button className="primary-button" onClick={handleSave} style={{ backgroundColor: 'var(--accent)' }}>
                        <Save size={16} /> Save & Apply
                    </button>
                </div>
                
                <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '1rem', marginBottom: 0 }}>
                    {isDrawing ? "Click on the video feed to place points. Click 'Finish Polygon' when done." : "Click 'Draw New Zone' to start adding detection areas."}
                </p>
            </div>
        </div>
    );
};

export default ZoneEditor;
