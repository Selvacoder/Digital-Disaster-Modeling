"use client";

import React from 'react';
import { Cpu, Flame, Navigation, History, LayoutGrid } from 'lucide-react';

export default function Sidebar({ isOpen, activeTab, setActiveTab }: {
    isOpen: boolean,
    activeTab: string,
    setActiveTab: (tab: any) => void
}) {
    const isDashboard = ['convert', 'simulate', 'damage', 'evacuate'].includes(activeTab);

    return (
        <aside className={`sidebar ${isOpen ? '' : 'closed'}`}>
            <div style={{ width: '280px', padding: '2rem', height: '100%', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
                <nav style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
                    <div
                        onClick={() => setActiveTab('convert')}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '0.75rem',
                            borderRadius: '10px',
                            background: isDashboard ? 'rgba(139, 92, 246, 0.1)' : 'transparent',
                            color: isDashboard ? '#a78bfa' : '#94a3b8',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                        }}
                    >
                        <LayoutGrid size={20} />
                        <span style={{ whiteSpace: 'nowrap', fontWeight: isDashboard ? 600 : 400 }}>Dashboard</span>
                    </div>
                    <div
                        onClick={() => setActiveTab('history')}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '0.75rem',
                            borderRadius: '10px',
                            background: activeTab === 'history' ? 'rgba(255,255,255,0.05)' : 'transparent',
                            color: activeTab === 'history' ? '#fff' : '#94a3b8',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                        }}
                    >
                        <History size={20} />
                        <span style={{ whiteSpace: 'nowrap', fontWeight: activeTab === 'history' ? 600 : 400 }}>History</span>
                    </div>
                    
                    <div style={{ height: '1px', background: 'rgba(255,255,255,0.05)', margin: '1rem 0' }}></div>

                    <div
                        style={{
                            padding: '0.75rem',
                            color: '#64748b',
                            fontSize: '0.75rem',
                            textTransform: 'uppercase',
                            letterSpacing: '0.05em',
                            fontWeight: 600
                        }}
                    >
                        Project Info
                    </div>
                    <p style={{ color: '#475569', fontSize: '0.85rem', padding: '0 0.75rem', lineHeight: 1.5 }}>
                        Digital Disaster Modeling system for blueprint analysis and safety planning.
                    </p>
                </nav>
            </div>
        </aside>
    );
}
