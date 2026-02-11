"use client";

import React, { useState } from 'react';
import { Settings, Play, Layers } from 'lucide-react';

interface ConfigPanelProps {
    onProcess: (config: {
        wallHeight: number,
        pixelScale: number,
        generateWalls: boolean,
        generateFloors: boolean,
        generateRooms: boolean,
        generateDetails: boolean
    }) => void;
    disabled: boolean;
}

export default function ConfigPanel({ onProcess, disabled }: ConfigPanelProps) {
    const [wallHeight, setWallHeight] = useState(2.5);
    const [pixelScale, setPixelScale] = useState(100);

    const [generateWalls, setGenerateWalls] = useState(true);
    const [generateFloors, setGenerateFloors] = useState(true);
    const [generateRooms, setGenerateRooms] = useState(true);
    const [generateDetails, setGenerateDetails] = useState(true);

    return (
        <div className="glass">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Settings size={20} color="#8b5cf6" />
                    <h3 style={{ margin: 0 }}>2. Configuration</h3>
                </div>
                <span style={{ fontSize: '0.7rem', padding: '2px 6px', background: '#8b5cf633', color: '#a78bfa', borderRadius: '4px', fontWeight: 600 }}>v1.2 CLEAN</span>
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.9rem', marginBottom: '0.5rem', color: '#94a3b8' }}>
                    Wall Height: {wallHeight}m
                </label>
                <input
                    type="range" min="2" max="5" step="0.1"
                    value={wallHeight}
                    onChange={(e) => setWallHeight(parseFloat(e.target.value))}
                    style={{ width: '100%', accentColor: '#8b5cf6', cursor: 'pointer' }}
                />
            </div>

            <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.9rem', marginBottom: '0.5rem', color: '#94a3b8' }}>
                    Pixel Scale: {pixelScale}
                </label>
                <input
                    type="range" min="50" max="200" step="10"
                    value={pixelScale}
                    onChange={(e) => setPixelScale(parseInt(e.target.value))}
                    style={{ width: '100%', accentColor: '#3b82f6', cursor: 'pointer' }}
                />
            </div>

            <div style={{ marginBottom: '2rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '1rem' }}>
                    <Layers size={16} color="#34d399" />
                    <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>Feature Toggles</span>
                </div>

                <div className="toggle-group" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.85rem',
                        color: '#cbd5e1',
                        cursor: 'pointer',
                        padding: '8px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '8px',
                        transition: 'all 0.2s'
                    }}>
                        <input type="checkbox" checked={generateWalls} onChange={e => setGenerateWalls(e.target.checked)} style={{ accentColor: '#3b82f6', width: '16px', height: '16px' }} />
                        Walls
                    </label>
                    <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.85rem',
                        color: '#cbd5e1',
                        cursor: 'pointer',
                        padding: '8px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '8px',
                        transition: 'all 0.2s'
                    }}>
                        <input type="checkbox" checked={generateFloors} onChange={e => setGenerateFloors(e.target.checked)} style={{ accentColor: '#3b82f6', width: '16px', height: '16px' }} />
                        Floors
                    </label>
                    <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.85rem',
                        color: '#cbd5e1',
                        cursor: 'pointer',
                        padding: '8px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '8px',
                        transition: 'all 0.2s'
                    }}>
                        <input type="checkbox" checked={generateRooms} onChange={e => setGenerateRooms(e.target.checked)} style={{ accentColor: '#3b82f6', width: '16px', height: '16px' }} />
                        Ceilings
                    </label>
                    <label style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        fontSize: '0.85rem',
                        color: '#cbd5e1',
                        cursor: 'pointer',
                        padding: '8px',
                        background: 'rgba(255,255,255,0.03)',
                        borderRadius: '8px',
                        transition: 'all 0.2s'
                    }}>
                        <input type="checkbox" checked={generateDetails} onChange={e => setGenerateDetails(e.target.checked)} style={{ accentColor: '#3b82f6', width: '16px', height: '16px' }} />
                        Openings
                    </label>
                </div>
            </div>

            <button
                className="btn-primary"
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}
                onClick={() => onProcess({ wallHeight, pixelScale, generateWalls, generateFloors, generateRooms, generateDetails })}
                disabled={disabled}
            >
                <Play size={18} />
                Generate 3D Model
            </button>
        </div>
    );
}
