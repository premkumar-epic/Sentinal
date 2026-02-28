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

export const getVideoStreamUrl = (cameraId) => {
    // Use relative URL for proxying through Vite, or absolute if direct
    return `${API_BASE_URL}/stream/${cameraId}`;
};
