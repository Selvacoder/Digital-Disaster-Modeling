"use client";

import React from 'react';
import { Bell, Search } from 'lucide-react';

export default function Header() {
    return (
        <header className="header">
            <div>
                <h2 style={{ margin: 0, fontSize: '1.8rem' }}>Welcome Back</h2>
                <p style={{ margin: 0, fontSize: '0.9rem' }}>Transform your 2D designs into 3D reality</p>
            </div>
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                    <Search size={18} style={{ position: 'absolute', left: '12px', color: '#64748b' }} />
                    <input
                        type="text"
                        placeholder="Search projects..."
                        style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '0.6rem 1rem 0.6rem 2.5rem', color: 'white', width: '250px' }}
                    />
                </div>
                <div style={{ background: 'rgba(255,255,255,0.05)', padding: '0.6rem', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.1)', cursor: 'pointer' }}>
                    <Bell size={20} color="#94a3b8" />
                </div>
            </div>
        </header>
    );
}
