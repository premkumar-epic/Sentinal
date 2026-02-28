import React from 'react';
import Dashboard from './pages/Dashboard';

function App() {
    return (
        <div className="app-container">
            <header>
                <div style={{ color: 'var(--accent)', display: 'flex', alignItems: 'center' }}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                    </svg>
                </div>
                <h1>SENTINAL<span style={{ color: 'var(--accent)' }}>v1</span> Dashboard</h1>
            </header>

            <main>
                <Dashboard />
            </main>
        </div>
    );
}

export default App;
