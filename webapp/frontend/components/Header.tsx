"use client";

import React from 'react';
import { Menu } from 'lucide-react';

export default function Header({ onToggleSidebar }: { onToggleSidebar: () => void }) {
    return (
        <header className="header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                <button
                    onClick={onToggleSidebar}
                    className="menu-toggle"
                >
                    <Menu size={20} />
                </button>
                <div className="logo" style={{ margin: 0, fontSize: '1.5rem' }}>FLOORPLAN 3D</div>
            </div>
        </header>
    );
}
