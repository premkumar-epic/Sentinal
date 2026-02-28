const API_BASE_URL = '/api';

export const fetchEvents = async (limit = 50) => {
    try {
        const response = await fetch(`${API_BASE_URL}/events?limit=${limit}`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error("Error fetching events:", error);
        return [];
    }
};

export const fetchZones = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/zones`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error("Error fetching zones:", error);
        return [];
    }
};

export const fetchStats = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/stats`);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error("Error fetching stats:", error);
        return { intrusions_24h: 0, unique_people_24h: 0, top_zone: "N/A" };
    }
};

export const updateZones = async (zones) => {
    const response = await fetch(`${API_BASE_URL}/zones`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(zones)
    });
    if (!response.ok) throw new Error('Failed to update zones');
    return await response.json();
};

export const fetchCameras = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/cameras`);
        if (!response.ok) return [];
        return await response.json();
    } catch {
        return [];
    }
};

export const startCamera = async (cameraId) => {
    await fetch(`${API_BASE_URL}/cameras/${cameraId}/start`, { method: "POST" });
};

export const getVideoStreamUrl = (cameraId) => {
    return `${API_BASE_URL}/stream/${cameraId}`;
};
