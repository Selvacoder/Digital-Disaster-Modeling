"use client";

import React from 'react';
import { History, LayoutGrid, HelpCircle, User } from 'lucide-react';

export default function Sidebar({ isOpen, activeTab, setActiveTab }: {
    isOpen: boolean,
    activeTab: string,
    setActiveTab: (tab: string) => void
}) {
    return (
        <aside className={`sidebar ${isOpen ? '' : 'closed'}`}>
            <div style={{ width: '280px', padding: '2rem', height: '100%', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
                <nav style={{ display: 'flex', flexDirection: 'column', gap: '1rem', flex: 1 }}>
                    <div
                        onClick={() => setActiveTab('dashboard')}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '0.75rem',
                            borderRadius: '10px',
                            background: activeTab === 'dashboard' ? 'rgba(255,255,255,0.05)' : 'transparent',
                            color: activeTab === 'dashboard' ? '#fff' : '#94a3b8',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                        }}
                    >
                        <LayoutGrid size={20} />
                        <span style={{ whiteSpace: 'nowrap' }}>Dashboard</span>
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
                        <span style={{ whiteSpace: 'nowrap' }}>History</span>
                    </div>
                </nav>
            </div>
        </aside>
    );
}
