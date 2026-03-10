"use client";

import React, { useState } from 'react';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import BlueprintUploader from '../components/BlueprintUploader';
import ConfigPanel from '../components/ConfigPanel';
import ThreeViewer from '../components/ThreeViewer';
import { Maximize, Minimize } from 'lucide-react';

export default function Home() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [modelUrl, setModelUrl] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [history, setHistory] = useState<any[]>([]);

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

  return (
    <div className="dashboard-container">
      <Sidebar
        isOpen={isSidebarOpen}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
      />
      <main className="main-content">
        <Header onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />

        {activeTab === 'dashboard' ? (
          <div className="content-dashboard">
            <div className="top-section">
              <BlueprintUploader onUpload={setUploadedFilename} />
              <ConfigPanel
                onProcess={handleProcess}
                disabled={!uploadedFilename || isProcessing}
              />
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
                      <ThreeViewer model={modelUrl} />
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
                        setActiveTab('dashboard');
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
