"use client";

import React, { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, ContactShadows, Grid, useGLTF } from '@react-three/drei';
import * as THREE from 'three';

function Model({ url, useBuiltinMaterials, onPointSelect, markers }: { 
    url: string | null, 
    useBuiltinMaterials?: boolean,
    onPointSelect?: (x: number, y: number, z: number) => void,
    markers?: {x: number, y: number, z: number, color: string}[]
}) {
    const { scene: obj } = useGLTF(url || '') as any;

    // Center and scale the model
    const mesh = useMemo(() => {
        if (!obj) return null;

        // Clone to avoid modifying the cached version
        const clonedObj = obj.clone();

        // Unified traverse function: Apply materials if missing or if forced
        clonedObj.traverse((child: any) => {
            if (child instanceof THREE.Mesh) {
                const name = child.name.toLowerCase();

                // Set double-sided rendering as a sane default
                if (child.material) {
                    if (Array.isArray(child.material)) {
                        child.material.forEach((m: any) => { m.side = THREE.DoubleSide; });
                    } else {
                        child.material.side = THREE.DoubleSide;
                    }
                }

                const isDefaultMat = !child.material || 
                                     child.material.name === "Default OBJ" || 
                                     child.material.name === "Material" || 
                                     child.material.name === "" ||
                                     child.material.name.startsWith("MaterialName");

                // Apply fallback materials if the user did not specify builtin materials OR if the material is missing/default
                if (!useBuiltinMaterials || isDefaultMat) {
                    let color = '#d4cfc7';
                    let roughness = 0.8;
                    let metalness = 0.1;

                    if (name.includes('wall')) {
                        color = '#f5f5dc'; // Beige/Off-white for house walls
                        roughness = 0.9;
                    } else if (name.includes('floor')) {
                        color = '#d2b48c'; // Tan/Oak for hardwood floors
                        roughness = 0.5;
                        metalness = 0.1;
                    } else if (name.includes('room')) {
                        color = '#eaddcf'; // Light beige for carpet/tile
                        roughness = 0.8;
                    } else if (name.includes('window')) {
                        color = '#aaccff'; // Reflective glass
                        roughness = 0.1;
                        metalness = 0.8;
                    } else if (name.includes('door')) {
                        color = '#8b5a2b'; // Brown wood for doors
                        roughness = 0.8;
                    }

                    child.material = new THREE.MeshStandardMaterial({
                        color: color,
                        roughness: roughness,
                        metalness: metalness,
                        side: THREE.DoubleSide
                    });
                }

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });

        // Center the model on X and Z, but keep Y at 0 (so it rests on the ground plane perfectly)
        const box = new THREE.Box3().setFromObject(clonedObj);
        const center = box.getCenter(new THREE.Vector3());
        clonedObj.position.x -= center.x;
        clonedObj.position.y = 0; // Lock to ground plane
        clonedObj.position.z -= center.z;

        return clonedObj;
    }, [obj, useBuiltinMaterials]);

    if (!url) return null;

    return mesh ? (
        <group>
            <primitive 
                object={mesh} 
                onClick={(e: any) => {
                    if (onPointSelect) {
                        e.stopPropagation();
                        // Transform from world space back to original blender local coordinates
                        onPointSelect(
                            e.point.x - mesh.position.x, 
                            e.point.y - mesh.position.y, 
                            e.point.z - mesh.position.z
                        );
                    }
                }}
            />
            {markers && markers.map((m, i) => (
                <mesh key={i} position={[m.x + mesh.position.x, m.y + mesh.position.y, m.z + mesh.position.z]}>
                    <sphereGeometry args={[0.5, 16, 16]} />
                    <meshStandardMaterial color={m.color} emissive={m.color} emissiveIntensity={1.5} />
                </mesh>
            ))}
        </group>
    ) : null;
}

function PlaceholderModel() {
    return (
        <mesh position={[0, 0.5, 0]}>
            <boxGeometry args={[2, 0.1, 2]} />
            <meshStandardMaterial color="#3b82f6" opacity={0.3} transparent />
        </mesh>
    );
}

export default function ThreeViewer({ model, isSimulated, onPointSelect, markers }: {
    model: string | null,
    isSimulated?: boolean,
    onPointSelect?: (x: number, y: number, z: number) => void,
    markers?: {x: number, y: number, z: number, color: string}[]
}) {
    return (
        <Canvas shadows dpr={[1, 2]} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}>
            <PerspectiveCamera makeDefault position={[12, 15, 15]} fov={50} />
            <OrbitControls
                makeDefault
                minPolarAngle={0}
                maxPolarAngle={Math.PI / 2.05}
                minDistance={4}
                maxDistance={150}
            />

            {/* Realistic Ambient and Directional Lighting */}
            <ambientLight intensity={0.5} />
            <directionalLight 
                castShadow 
                position={[15, 25, 10]} 
                intensity={1.5} 
                shadow-mapSize-width={2048} 
                shadow-mapSize-height={2048} 
                shadow-camera-near={0.5}
                shadow-camera-far={100} 
                shadow-camera-left={-25} 
                shadow-camera-right={25} 
                shadow-camera-top={25} 
                shadow-camera-bottom={-25} 
                shadow-bias={-0.0005}
            />
            <pointLight position={[-15, 10, -15]} intensity={0.6} color="#8da6d1" />

            <Suspense fallback={<PlaceholderModel />}>
                {model ? (
                    <group>
                        <Model url={model} useBuiltinMaterials={isSimulated} onPointSelect={onPointSelect} markers={markers} />
                    </group>
                ) : (
                    <group position={[0, 0.5, 0]}>
                        <mesh receiveShadow castShadow>
                            <boxGeometry args={[2, 0.05, 2]} />
                            <meshStandardMaterial color="#1e293b" roughness={0.6} />
                        </mesh>
                    </group>
                )}

                {/* Ground Plane (Grassy Plot) for Contrast and Shadow Reception */}
                <mesh receiveShadow position={[0, -0.01, 0]} rotation={[-Math.PI / 2, 0, 0]}>
                    <planeGeometry args={[200, 200]} />
                    <meshStandardMaterial color="#4f5f4f" roughness={1.0} metalness={0.0} />
                </mesh>

                <Grid
                    position={[0, 0.0, 0]}
                    infiniteGrid
                    fadeDistance={50}
                    fadeStrength={5}
                    sectionColor="#3b4d3b"
                    cellColor="#2f3d2f"
                    sectionSize={5}
                    cellSize={1}
                />

                {/* HDR Environment Lighting for realistic reflections */}
                <Environment preset="city" background={false} />
            </Suspense>
        </Canvas>
    );
}
