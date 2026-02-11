"use client";

import React, { useState } from 'react';
import { Upload, X, Loader2 } from 'lucide-react';

export default function BlueprintUploader({ onUpload }: { onUpload: (filename: string | null) => void }) {
    const [preview, setPreview] = useState<string | null>(null);
    const [dragging, setDragging] = useState(false);
    const [isUploading, setIsUploading] = useState(false);

    const handleFileUpload = async (file: File) => {
        if (!file || !file.type.startsWith('image/')) return;

        // Show local preview
        const reader = new FileReader();
        reader.onload = (e) => setPreview(e.target?.result as string);
        reader.readAsDataURL(file);

        // Upload to server
        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('http://localhost:8000/upload', {
                method: 'POST',
                body: formData,
            });
            const data = await response.json();
            onUpload(data.filename);
        } catch (error) {
            console.error('Upload failed:', error);
            alert('Failed to upload image. Is the backend running?');
        } finally {
            setIsUploading(false);
        }
    };

    return (
        <div className="glass" style={{ marginBottom: '2rem' }}>
            <h3>1. Upload Blueprint</h3>
            {!preview ? (
                <div
                    className={`upload-area ${dragging ? 'dragging' : ''} ${isUploading ? 'opacity-50' : ''}`}
                    onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={(e) => {
                        e.preventDefault();
                        setDragging(false);
                        if (e.dataTransfer.files[0]) handleFileUpload(e.dataTransfer.files[0]);
                    }}
                    onClick={() => !isUploading && document.getElementById('fileInput')?.click()}
                >
                    {isUploading ? (
                        <Loader2 className="animate-spin" size={48} color="#3b82f6" style={{ marginBottom: '1rem' }} />
                    ) : (
                        <Upload size={48} color="#3b82f6" style={{ marginBottom: '1rem' }} />
                    )}
                    <p>{isUploading ? 'Uploading...' : 'Drag and drop your 2D blueprint here'}</p>
                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>Supports PNG, JPG (Top-down view)</span>
                    <input
                        type="file"
                        id="fileInput"
                        hidden
                        onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
                    />
                </div>
            ) : (
                <div style={{ position: 'relative' }}>
                    <img src={preview} alt="Preview" style={{ width: '100%', borderRadius: '12px', display: 'block' }} />
                    <button
                        disabled={isUploading}
                        onClick={() => { setPreview(null); onUpload(null); }}
                        style={{
                            position: 'absolute', top: '10px', right: '10px',
                            background: 'rgba(0,0,0,0.5)', border: 'none', borderRadius: '50%',
                            padding: '5px', cursor: 'pointer', color: 'white'
                        }}
                    >
                        <X size={20} />
                    </button>
                </div>
            )}
        </div>
    );
}
