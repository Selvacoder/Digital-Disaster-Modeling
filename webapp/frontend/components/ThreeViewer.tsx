"use client";

import React, { Suspense, useMemo } from 'react';
import { Canvas, useLoader } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, ContactShadows, Grid } from '@react-three/drei';
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js';
import * as THREE from 'three';

function Model({ url }: { url: string | null }) {
    const obj = useLoader(OBJLoader, url || '');

    // Center and scale the model
    const mesh = useMemo(() => {
        if (!obj) return null;

        // Clone to avoid modifying the cached version
        const clonedObj = obj.clone();

        // Apply high-contrast materials based on mesh names (Wall, Floor, Room, etc.)
        clonedObj.traverse((child) => {
            if (child instanceof THREE.Mesh) {
                const name = child.name.toLowerCase();

                let color = '#cbd5e1'; // Default grey
                let roughness = 0.5;
                let metalness = 0.1;

                if (name.includes('wall')) {
                    color = '#334155'; // Dark slate/charcoal for walls
                    roughness = 0.8;
                } else if (name.includes('floor')) {
                    color = '#f1f5f9'; // Very light grey/white for floor
                    roughness = 0.4;
                } else if (name.includes('room')) {
                    color = '#e2e8f0'; // Light grey for ceilings/rooms
                    roughness = 0.6;
                } else if (name.includes('window')) {
                    color = '#bae6fd'; // Light blue for windows
                    roughness = 0.1;
                    metalness = 0.5;
                } else if (name.includes('door')) {
                    color = '#92400e'; // Brown for doors
                    roughness = 0.9;
                }

                child.material = new THREE.MeshStandardMaterial({
                    color: color,
                    roughness: roughness,
                    metalness: metalness,
                    side: THREE.DoubleSide
                });

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });

        // Center the model
        const box = new THREE.Box3().setFromObject(clonedObj);
        const center = box.getCenter(new THREE.Vector3());
        clonedObj.position.x -= center.x;
        clonedObj.position.y -= box.min.y; // Sit on the ground
        clonedObj.position.z -= center.z;

        return clonedObj;
    }, [obj]);

    if (!url) return null;

    return mesh ? <primitive object={mesh} /> : null;
}

function PlaceholderModel() {
    return (
        <mesh position={[0, 0.5, 0]}>
            <boxGeometry args={[2, 0.1, 2]} />
            <meshStandardMaterial color="#3b82f6" opacity={0.3} transparent />
        </mesh>
    );
}

export default function ThreeViewer({ model }: { model: string | null }) {
    return (
        <Canvas shadows dpr={[1, 2]}>
            <PerspectiveCamera makeDefault position={[8, 8, 8]} fov={50} />
            <OrbitControls makeDefault minPolarAngle={0} maxPolarAngle={Math.PI / 2.1} />

            <ambientLight intensity={0.7} />
            <spotLight position={[10, 15, 10]} angle={0.3} penumbra={1} intensity={2} castShadow />
            <pointLight position={[-10, -10, -10]} intensity={0.5} />

            <Suspense fallback={<PlaceholderModel />}>
                {model ? (
                    <Model url={model} />
                ) : (
                    <group position={[0, 0.5, 0]}>
                        <mesh>
                            <boxGeometry args={[2, 0.05, 2]} />
                            <meshStandardMaterial color="#1e293b" />
                        </mesh>
                        <Grid
                            infiniteGrid
                            fadeDistance={20}
                            fadeStrength={5}
                            sectionColor="#3b82f6"
                            cellColor="#1e293b"
                            sectionSize={5}
                            cellSize={1}
                        />
                    </group>
                )}
                <Environment preset="city" />
                <ContactShadows position={[0, 0, 0]} opacity={0.4} scale={20} blur={2.4} far={4.5} />
            </Suspense>
        </Canvas>
    );
}
