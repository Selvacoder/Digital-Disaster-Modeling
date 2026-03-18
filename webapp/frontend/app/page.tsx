"use client";

import React, { useState } from 'react';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import BlueprintUploader from '../components/BlueprintUploader';
import ConfigPanel from '../components/ConfigPanel';
import ThreeViewer from '../components/ThreeViewer';
import { Maximize, Minimize, Cpu, Flame, Navigation, History, LayoutGrid } from 'lucide-react';

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [activeTab, setActiveTab] = useState('convert');
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [history, setHistory] = useState<any[]>([]);
  const [simulationData, setSimulationData] = useState<any>(null);
  const [evacuationPath, setEvacuationPath] = useState<any[]>([]);
  const [disasterType, setDisasterType] = useState('fire');
  // Advanced Simulation State
  const [windSpeed, setWindSpeed] = useState(15);
  const [ambientTemp, setAmbientTemp] = useState(25);
  const [waterLevel, setWaterLevel] = useState(1.5);
  const [rainfallRate, setRainfallRate] = useState(20);
  const [magnitude, setMagnitude] = useState(5.5);
  const [depth, setDepth] = useState(10);
  // Evacuation origin coordinates
  const [originX, setOriginX] = useState(0);
  const [originY, setOriginY] = useState(0);

  const viewerRef = React.useRef<HTMLDivElement>(null);

  const fetchHistory = async () => {
    try {
      const response = await fetch('http://localhost:8000/history');
      const data = await response.json();
      setHistory(data);
    } catch (err) {
      console.error('Failed to fetch history:', err);
    }
  };

  React.useEffect(() => {
    if (activeTab === 'history') {
      fetchHistory();
    }
  }, [activeTab]);

  const toggleFullscreen = () => {
    if (!viewerRef.current) return;

    if (!document.fullscreenElement) {
      viewerRef.current.requestFullscreen().catch(err => {
        console.error(`Error attempting to enable full-screen mode: ${err.message}`);
      });
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // Sync state if user exits via ESC
  React.useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  const handleProcess = async (config: {
    wallHeight: number,
    pixelScale: number,
    generateWalls: boolean,
    generateFloors: boolean,
    generateRooms: boolean,
    generateDetails: boolean
  }) => {
    if (!uploadedFilename) return;

    setIsProcessing(true);
    setModelUrl(null);

    const formData = new FormData();
    formData.append('filename', uploadedFilename);
    formData.append('wall_height', config.wallHeight.toString());
    formData.append('pixel_scale', config.pixelScale.toString());
    formData.append('generate_walls', config.generateWalls.toString());
    formData.append('generate_floors', config.generateFloors.toString());
    formData.append('generate_rooms', config.generateRooms.toString());
    formData.append('generate_details', config.generateDetails.toString());

    try {
      const response = await fetch('http://localhost:8000/convert', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('Conversion failed');

      const data = await response.json();
      // Add a small delay for dramatic effect 
      setTimeout(() => {
        const fullModelUrl = `http://localhost:8000${data.model_url}`;
        setModelUrl(`${fullModelUrl}&t=${Date.now()}`);
        setIsProcessing(false);
      }, 1500);

    } catch (error) {
      console.error('Processing failed:', error);
      alert('Failed to convert blueprint. Check backend logs.');
      setIsProcessing(false);
    }
  };

  const handleSimulate = async () => {
    if (!uploadedFilename) return;
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('filename', uploadedFilename);
    formData.append('disaster_type', disasterType);
    
    // Add advanced params based on type
    if (disasterType === 'fire') {
      formData.append('wind_speed', windSpeed.toString());
      formData.append('ambient_temp', ambientTemp.toString());
    } else if (disasterType === 'flood') {
      formData.append('water_level', waterLevel.toString());
      formData.append('rainfall_rate', rainfallRate.toString());
    } else if (disasterType === 'earthquake') {
      formData.append('magnitude', magnitude.toString());
      formData.append('depth', depth.toString());
    }

    try {
      const response = await fetch('http://localhost:8000/simulate', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Simulation failed');
      }
      const data = await response.json();
      // Load the real simulated model into the viewer
      const simulatedModelUrl = `http://localhost:8000${data.model_url}`;
      setModelUrl(simulatedModelUrl);
      setSimulationData(data);
    } catch (error: any) {
      console.error('Simulation failed:', error);
      alert(error.message || 'Simulation failed. Check backend logs.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePathfind = async () => {
    if (!uploadedFilename) return;
    setIsProcessing(true);

    const formData = new FormData();
    formData.append('filename', uploadedFilename);
    formData.append('start_x', originX.toString());
    formData.append('start_y', originY.toString());

    try {
      const response = await fetch('http://localhost:8000/pathfind', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Pathfinding failed');
      }
      const data = await response.json();
      // Load the real evacuated model with path baked in
      const evacuatedModelUrl = `http://localhost:8000${data.model_url}`;
      setModelUrl(evacuatedModelUrl);
      setEvacuationPath([]);
    } catch (error: any) {
      console.error('Pathfinding failed:', error);
      alert(error.message || 'Pathfinding failed. Check backend logs.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="dashboard-container">
      <Sidebar
        isOpen={isSidebarOpen}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
      <main className="main-content">
        <Header onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />

        {['convert', 'simulate', 'evacuate'].includes(activeTab) && (
          <div className="tabs-container glass" style={{ 
            margin: '1.5rem 2rem', 
            padding: '0.5rem', 
            display: 'flex', 
            gap: '10px',
            borderRadius: '12px',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            {[
              { id: 'convert', label: '1. Convert', icon: <Cpu size={18} /> },
              { id: 'simulate', label: '2. Simulate', icon: <Flame size={18} /> },
              { id: 'evacuate', label: '3. Evacuate', icon: <Navigation size={18} /> }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`tab-btn ${activeTab === tab.id ? 'active' : ''}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '0.6rem 1.5rem',
                  borderRadius: '8px',
                  border: 'none',
                  background: activeTab === tab.id ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                  color: activeTab === tab.id ? '#a78bfa' : '#94a3b8',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  fontWeight: 500,
                  fontSize: '0.9rem'
                }}
              >
                {tab.icon}
                {tab.label}
              </button>
            ))}
          </div>
        )}
        {['convert', 'simulate', 'evacuate'].includes(activeTab) ? (
          <div className="content-dashboard">
            <div className="top-section">
              {activeTab === 'convert' && (
                <>
                  <BlueprintUploader onUpload={setUploadedFilename} />
                  <ConfigPanel
                    onProcess={handleProcess}
                    disabled={!uploadedFilename || isProcessing}
                  />
                </>
              )}
              {activeTab === 'simulate' && (
                <div className="glass" style={{ flex: 1, padding: '2rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1.5rem' }}>
                    <Flame size={20} color="#ef4444" />
                    <h3 style={{ margin: 0 }}>Disaster Simulation</h3>
                  </div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                    {/* Left Column: Core Parameters */}
                    <div style={{ paddingRight: '1rem', borderRight: '1px solid rgba(255,255,255,0.05)' }}>
                      <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                        Core disaster selection and main intensity controls.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        <div>
                          <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Disaster Type</label>
                          <select 
                            value={disasterType}
                            onChange={(e) => setDisasterType(e.target.value)}
                            style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', padding: '0.75rem', borderRadius: '8px' }}>
                            <option value="fire">🔥 Fire Outbreak</option>
                            <option value="flood">🌊 Flash Flood</option>
                            <option value="earthquake">🏚️ Earthquake</option>
                          </select>
                        </div>
                        <button 
                          onClick={handleSimulate}
                          disabled={!uploadedFilename || isProcessing}
                          className="btn-primary" 
                          style={{ background: '#ef4444', marginTop: '1rem', opacity: (!uploadedFilename || isProcessing) ? 0.5 : 1 }}>
                          {isProcessing ? 'Simulating...' : 'Start Global Simulation'}
                        </button>
                      </div>
                    </div>

                    {/* Right Column: Detailed Parameters */}
                    <div>
                      <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
                        Detailed environmental parameters for {disasterType}.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
                        {disasterType === 'fire' && (
                          <>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Wind Speed (km/h): {windSpeed}</label>
                              <input type="range" min="0" max="100" value={windSpeed} onChange={(e) => setWindSpeed(parseInt(e.target.value))} style={{ width: '100%', accentColor: '#f97316' }} />
                            </div>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Ambient Temp (°C): {ambientTemp}</label>
                              <input type="range" min="0" max="60" value={ambientTemp} onChange={(e) => setAmbientTemp(parseInt(e.target.value))} style={{ width: '100%', accentColor: '#f97316' }} />
                            </div>
                          </>
                        )}
                        {disasterType === 'flood' && (
                          <>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Expected Water Level (m): {waterLevel}</label>
                              <input type="range" step="0.1" min="0" max="10" value={waterLevel} onChange={(e) => setWaterLevel(parseFloat(e.target.value))} style={{ width: '100%', accentColor: '#3b82f6' }} />
                            </div>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Rainfall Rate (mm/h): {rainfallRate}</label>
                              <input type="range" min="0" max="100" value={rainfallRate} onChange={(e) => setRainfallRate(parseInt(e.target.value))} style={{ width: '100%', accentColor: '#3b82f6' }} />
                            </div>
                          </>
                        )}
                        {disasterType === 'earthquake' && (
                          <>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Magnitude (Richter): {magnitude}</label>
                              <input type="range" step="0.1" min="1" max="10" value={magnitude} onChange={(e) => setMagnitude(parseFloat(e.target.value))} style={{ width: '100%', accentColor: '#fbbf24' }} />
                            </div>
                            <div>
                              <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Focal Depth (km): {depth}</label>
                              <input type="range" min="0" max="50" value={depth} onChange={(e) => setDepth(parseInt(e.target.value))} style={{ width: '100%', accentColor: '#fbbf24' }} />
                            </div>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
              {activeTab === 'evacuate' && (
                <div className="glass" style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '1.5rem' }}>
                    <Navigation size={20} color="#10b981" />
                    <h3 style={{ margin: 0 }}>Evacuation Planner</h3>
                  </div>
                  <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                    Set a starting point and find the fastest route to the nearest exit using A* pathfinding on the real 3D model.
                  </p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Origin X</label>
                        <input 
                          type="number" step="0.5"
                          value={originX}
                          onChange={(e) => setOriginX(parseFloat(e.target.value) || 0)}
                          style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', padding: '0.75rem', borderRadius: '8px', boxSizing: 'border-box' }} 
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.5rem', color: '#64748b' }}>Origin Y</label>
                        <input 
                          type="number" step="0.5"
                          value={originY}
                          onChange={(e) => setOriginY(parseFloat(e.target.value) || 0)}
                          style={{ width: '100%', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: 'white', padding: '0.75rem', borderRadius: '8px', boxSizing: 'border-box' }} 
                        />
                      </div>
                    </div>
                    <button 
                      onClick={handlePathfind}
                      disabled={!uploadedFilename || isProcessing}
                      className="btn-primary" 
                      style={{ background: '#10b981', marginTop: '1rem', opacity: (!uploadedFilename || isProcessing) ? 0.5 : 1 }}>
                      {isProcessing ? 'Calculating...' : 'Calculate Path'}
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="bottom-section">
              <div className="viewer-card glass" style={{ height: isFullscreen ? '100%' : '600px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                  <h3 style={{ margin: 0 }}>3D Result Preview</h3>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={toggleFullscreen}
                      className="menu-toggle"
                      style={{ padding: '0.4rem', border: 'none', background: 'rgba(255,255,255,0.05)' }}
                      title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
                    >
                      {isFullscreen ? <Minimize size={18} /> : <Maximize size={18} />}
                    </button>
                  </div>
                </div>
                <div className="viewer-wrapper" ref={viewerRef}>
                  {isProcessing ? (
                    <div className="loading-overlay">
                      <div className="spinner"></div>
                      <p>Generating 3D Magic...</p>
                    </div>
                  ) : (
                    <>
                       <ThreeViewer 
                        model={modelUrl} 
                        isSimulated={!!simulationData || evacuationPath.length > 0}
                      />
                      {modelUrl && (
                        <a
                          href={modelUrl}
                          download
                          className="btn-primary"
                          style={{
                            position: 'absolute',
                            bottom: '20px',
                            right: '20px',
                            padding: '0.6rem 1.2rem',
                            fontSize: '0.85rem',
                            textDecoration: 'none',
                            zIndex: 10,
                            boxShadow: '0 4px 15px rgba(0,0,0,0.3)'
                          }}
                        >
                          Download OBJ
                        </a>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="history-view">
            <h2 style={{ marginBottom: '2rem' }}>Project History</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '2rem' }}>
              {history.map((item) => (
                <div key={item.id} className="glass" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <div style={{ height: '180px', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    {item.preview_url ? (
                      <img
                        src={`http://localhost:8000${item.preview_url}`}
                        alt="Preview"
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                    ) : (
                      <div style={{ color: '#64748b', textAlign: 'center' }}>
                        <p style={{ margin: 0 }}>No Preview Available</p>
                      </div>
                    )}
                  </div>
                  <div>
                    <h4 style={{ margin: '0 0 0.5rem 0', color: '#fff' }}>Project {item.id.substring(0, 8)}</h4>
                    <p style={{ margin: 0, fontSize: '0.85rem' }}>
                      {new Date(item.timestamp * 1000).toLocaleDateString()} at {new Date(item.timestamp * 1000).toLocaleTimeString()}
                    </p>
                    <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.8rem', opacity: 0.6 }}>
                      Size: {(item.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <div style={{ display: 'flex', gap: '1rem', marginTop: 'auto' }}>
                    <button
                      onClick={() => {
                        setModelUrl(`http://localhost:8000${item.model_url}?t=${Date.now()}`);
                        setActiveTab('convert');
                      }}
                      className="btn-primary"
                      style={{ flex: 1, padding: '0.6rem', fontSize: '0.9rem' }}
                    >
                      Reload in 3D
                    </button>
                    <a
                      href={`http://localhost:8000${item.model_url}`}
                      download
                      className="menu-toggle"
                      style={{ padding: '0.6rem', border: '1px solid rgba(255,255,255,0.1)', flex: '0 0 auto', textDecoration: 'none' }}
                      title="Download OBJ"
                    >
                      <Maximize size={18} />
                    </a>
                  </div>
                </div>
              ))}
              {history.length === 0 && (
                <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '4rem', color: '#64748b' }}>
                  <h3>No past projects found.</h3>
                  <p>Start by uploading a blueprint in the dashboard!</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
