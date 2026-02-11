"use client";

import React, { useState } from 'react';
import Header from '../components/Header';
import Sidebar from '../components/Sidebar';
import BlueprintUploader from '../components/BlueprintUploader';
import ConfigPanel from '../components/ConfigPanel';
import ThreeViewer from '../components/ThreeViewer';

export default function Home() {
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [modelUrl, setModelUrl] = useState<string | null>(null);

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
        setModelUrl(`http://localhost:8000${data.model_url}?t=${Date.now()}`);
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
      <Sidebar />
      <main className="main-content">
        <Header />
        <div className="content-grid">
          <div className="dashboard-left">
            <BlueprintUploader onUpload={setUploadedFilename} />
            <ConfigPanel
              onProcess={handleProcess}
              disabled={!uploadedFilename || isProcessing}
            />
          </div>
          <div className="dashboard-right">
            <div className="viewer-card glass">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <h3 style={{ margin: 0 }}>3D Result Preview</h3>
                {modelUrl && (
                  <a
                    href={modelUrl}
                    download
                    className="btn-primary"
                    style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', textDecoration: 'none' }}
                  >
                    Download OBJ
                  </a>
                )}
              </div>
              <div className="viewer-wrapper">
                {isProcessing ? (
                  <div className="loading-overlay">
                    <div className="spinner"></div>
                    <p>Generating 3D Magic...</p>
                  </div>
                ) : (
                  <ThreeViewer model={modelUrl} />
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
