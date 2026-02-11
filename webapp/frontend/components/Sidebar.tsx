"use client";

import React from 'react';
import { History, LayoutGrid, HelpCircle, User } from 'lucide-react';

export default function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="logo">FLOORPLAN 3D</div>
            <nav style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '0.75rem', borderRadius: '10px', background: 'rgba(255,255,255,0.05)', color: '#fff', cursor: 'pointer' }}>
                    <LayoutGrid size={20} />
                    <span>Dashboard</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '0.75rem', borderRadius: '10px', color: '#94a3b8', cursor: 'pointer' }}>
                    <History size={20} />
                    <span>History</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '0.75rem', borderRadius: '10px', color: '#94a3b8', cursor: 'pointer' }}>
                    <User size={20} />
                    <span>Account</span>
                </div>
                <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '12px', padding: '0.75rem', borderRadius: '10px', color: '#94a3b8', cursor: 'pointer' }}>
                    <HelpCircle size={20} />
                    <span>Help Center</span>
                </div>
            </nav>
        </aside>
    );
}
