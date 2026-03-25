"use client";

import React, { Suspense, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera, Environment, ContactShadows, Grid, useGLTF, Html } from '@react-three/drei';
import * as THREE from 'three';

type DamageOverlay = {
    enabled?: boolean;
    roomTypeSeverity?: Record<string, number>;
};

type AreaLabel = {
    name: string;
    x: number;
    y: number;
    z: number;
};

type RoomCenter = {
    x: number;
    z: number;
    area: number;
};

function extractRoomCenters(root: THREE.Object3D): RoomCenter[] {
    const centers: RoomCenter[] = [];
    root.traverse((child: any) => {
        if (!(child instanceof THREE.Mesh)) return;
        const n = String(child.name || '').toLowerCase();
        if (!n.includes('room')) return;
        const box = new THREE.Box3().setFromObject(child);
        const c = box.getCenter(new THREE.Vector3());
        const size = box.getSize(new THREE.Vector3());
        const footprint = Math.max(0.01, size.x * size.z);
        if (Number.isFinite(c.x) && Number.isFinite(c.z)) {
            centers.push({ x: c.x, z: c.z, area: footprint });
        }
    });

    // Merge nearby room meshes into a single anchor to avoid duplicate labels per room.
    const clusters: Array<{ x: number; z: number; area: number; count: number }> = [];
    const MERGE_DIST = 0.9;
    for (const c of centers) {
        let merged = false;
        for (const cl of clusters) {
            const dx = c.x - cl.x;
            const dz = c.z - cl.z;
            if (dx * dx + dz * dz <= MERGE_DIST * MERGE_DIST) {
                const w1 = cl.area;
                const w2 = c.area;
                const w = Math.max(0.01, w1 + w2);
                cl.x = (cl.x * w1 + c.x * w2) / w;
                cl.z = (cl.z * w1 + c.z * w2) / w;
                cl.area = Math.max(cl.area, c.area);
                cl.count += 1;
                merged = true;
                break;
            }
        }
        if (!merged) {
            clusters.push({ x: c.x, z: c.z, area: c.area, count: 1 });
        }
    }

    return clusters
        .sort((a, b) => b.area - a.area)
        .map((c) => ({ x: c.x, z: c.z, area: c.area }));
}

function parseAreaIndex(name: string): number {
    const m = /^\s*area\s*[-_]?\s*(\d+)\s*$/i.exec(name || '');
    return m ? Number(m[1]) : Number.POSITIVE_INFINITY;
}

function mapLabelsToRoomAnchors(labels: AreaLabel[], roomAnchors: RoomCenter[]): AreaLabel[] | null {
    if (!labels.length || !roomAnchors.length) return null;
    const sortedLabels = [...labels].sort((a, b) => parseAreaIndex(a.name) - parseAreaIndex(b.name));
    const count = Math.min(sortedLabels.length, roomAnchors.length);
    if (count === 0) return null;

    const mapped: AreaLabel[] = [];
    for (let i = 0; i < count; i++) {
        mapped.push({
            ...sortedLabels[i],
            x: roomAnchors[i].x,
            z: roomAnchors[i].z,
        });
    }

    // Keep any extra labels (if present) after mapped ones.
    for (let i = count; i < sortedLabels.length; i++) {
        mapped.push(sortedLabels[i]);
    }
    return mapped;
}

function rotatePointAroundCenter(px: number, pz: number, cx: number, cz: number, deg: number) {
    const r = (deg * Math.PI) / 180;
    const dx = px - cx;
    const dz = pz - cz;
    const rx = dx * Math.cos(r) - dz * Math.sin(r);
    const rz = dx * Math.sin(r) + dz * Math.cos(r);
    return { x: cx + rx, z: cz + rz };
}

function declutterLabels(labels: AreaLabel[], minDist = 0.75, maxShift = 0.45): AreaLabel[] {
    const out = labels.map((l) => ({ ...l, _ax: l.x, _az: l.z } as any));
    for (let it = 0; it < 30; it++) {
        for (let i = 0; i < out.length; i++) {
            for (let j = i + 1; j < out.length; j++) {
                const dx = out[j].x - out[i].x;
                const dz = out[j].z - out[i].z;
                const d2 = dx * dx + dz * dz;
                if (d2 <= 1e-6) continue;
                if (d2 < minDist * minDist) {
                    const d = Math.sqrt(d2);
                    const push = (minDist - d) * 0.5;
                    const nx = dx / d;
                    const nz = dz / d;
                    out[i].x -= nx * push;
                    out[i].z -= nz * push;
                    out[j].x += nx * push;
                    out[j].z += nz * push;
                }
            }
        }

        // Keep labels close to anchors.
        for (const p of out) {
            const adx = p.x - p._ax;
            const adz = p.z - p._az;
            const ad = Math.sqrt(adx * adx + adz * adz);
            if (ad > maxShift && ad > 1e-6) {
                p.x = p._ax + (adx / ad) * maxShift;
                p.z = p._az + (adz / ad) * maxShift;
            }
        }
    }

    return out.map((p: any) => ({ name: p.name, x: p.x, y: p.y, z: p.z }));
}

function alignLabelsToRooms(labels: AreaLabel[], rooms: RoomCenter[]): AreaLabel[] {
    if (!labels.length || !rooms.length) return labels;

    const labelCx = labels.reduce((s, p) => s + p.x, 0) / labels.length;
    const labelCz = labels.reduce((s, p) => s + p.z, 0) / labels.length;
    const roomCx = rooms.reduce((s, p) => s + p.x, 0) / rooms.length;
    const roomCz = rooms.reduce((s, p) => s + p.z, 0) / rooms.length;

    const candidateAngles = [0, 90, 180, 270];
    let best: { score: number; points: AreaLabel[] } | null = null;

    for (const angle of candidateAngles) {
        // Rotate labels around their centroid first.
        const rotated = labels.map((l) => {
            const r = rotatePointAroundCenter(l.x, l.z, labelCx, labelCz, angle);
            return { ...l, x: r.x, z: r.z };
        });

        // Fit scale in X/Z from bounding boxes.
        const lxMin = Math.min(...rotated.map((p) => p.x));
        const lxMax = Math.max(...rotated.map((p) => p.x));
        const lzMin = Math.min(...rotated.map((p) => p.z));
        const lzMax = Math.max(...rotated.map((p) => p.z));
        const rxMin = Math.min(...rooms.map((p) => p.x));
        const rxMax = Math.max(...rooms.map((p) => p.x));
        const rzMin = Math.min(...rooms.map((p) => p.z));
        const rzMax = Math.max(...rooms.map((p) => p.z));

        const lWidth = Math.max(0.01, lxMax - lxMin);
        const lDepth = Math.max(0.01, lzMax - lzMin);
        const rWidth = Math.max(0.01, rxMax - rxMin);
        const rDepth = Math.max(0.01, rzMax - rzMin);
        const sx = rWidth / lWidth;
        const sz = rDepth / lDepth;

        const transformed = rotated.map((l) => ({
            ...l,
            x: (l.x - labelCx) * sx + roomCx,
            z: (l.z - labelCz) * sz + roomCz,
        }));

        let score = 0;

        for (const l of transformed) {
            let bestDist = Number.POSITIVE_INFINITY;
            for (let i = 0; i < rooms.length; i++) {
                const dx = l.x - rooms[i].x;
                const dz = l.z - rooms[i].z;
                const d2 = dx * dx + dz * dz;
                if (d2 < bestDist) {
                    bestDist = d2;
                }
            }
            score += bestDist;
        }

        if (!best || score < best.score) {
            best = { score, points: transformed };
        }
    }

    return best ? declutterLabels(best.points) : labels;
}

function getMeshRoomType(name: string): string | null {
    const n = name.toLowerCase();
    if (n.includes('kitchen')) return 'kitchen';
    if (n.includes('bed')) return 'bedroom';
    if (n.includes('bath')) return 'bathroom';
    if (n.includes('living') || n.includes('lounge')) return 'living';
    if (n.includes('hall') || n.includes('corridor')) return 'hallway';
    if (n.includes('garage')) return 'garage';
    if (n.includes('store') || n.includes('storage') || n.includes('closet')) return 'storage';
    if (n.includes('room')) return 'unknown';
    return null;
}

function severityToColorHex(severity: number): string {
    const t = Math.max(0, Math.min(1, severity / 100));
    const cold = new THREE.Color('#22c55e');
    const warm = new THREE.Color('#f59e0b');
    const hot = new THREE.Color('#ef4444');
    const out = new THREE.Color();

    if (t < 0.5) {
        out.copy(cold).lerp(warm, t / 0.5);
    } else {
        out.copy(warm).lerp(hot, (t - 0.5) / 0.5);
    }
    return `#${out.getHexString()}`;
}

function Model({ url, useBuiltinMaterials, onPointSelect, markers, damageOverlay, areaLabels }: { 
    url: string | null, 
    useBuiltinMaterials?: boolean,
    onPointSelect?: (x: number, y: number, z: number) => void,
    markers?: {x: number, y: number, z: number, color: string}[],
    damageOverlay?: DamageOverlay,
    areaLabels?: AreaLabel[],
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

                // Optional damage overlay by room type, using prediction severities.
                if (damageOverlay?.enabled && damageOverlay.roomTypeSeverity) {
                    const roomType = getMeshRoomType(name);
                    if (roomType) {
                        const severity = damageOverlay.roomTypeSeverity[roomType]
                            ?? damageOverlay.roomTypeSeverity['unknown']
                            ?? null;
                        if (severity !== null) {
                            const damageColor = severityToColorHex(severity);
                            child.material = new THREE.MeshStandardMaterial({
                                color: damageColor,
                                roughness: 0.65,
                                metalness: 0.1,
                                emissive: damageColor,
                                emissiveIntensity: 0.1 + Math.min(0.35, severity / 250),
                                side: THREE.DoubleSide,
                            });
                        }
                    }
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
    }, [obj, useBuiltinMaterials, damageOverlay]);

    const alignedAreaLabels = useMemo(() => {
        if (!mesh || !areaLabels || areaLabels.length === 0) return areaLabels || [];
        const roomCenters = extractRoomCenters(mesh);
        if (roomCenters.length === 0) return areaLabels;

        // First try deterministic Area-N -> Nth largest room anchor mapping from model geometry.
        const mapped = mapLabelsToRoomAnchors(areaLabels, roomCenters);
        if (mapped && mapped.length) {
            return declutterLabels(mapped, 0.62, 0.32);
        }

        // Fallback to transform-fit alignment.
        return alignLabelsToRooms(areaLabels, roomCenters);
    }, [mesh, areaLabels]);

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
            {alignedAreaLabels && alignedAreaLabels.map((area, i) => (
                <group key={`area-label-${i}`} position={[area.x + mesh.position.x, area.y + mesh.position.y, area.z + mesh.position.z]}>
                    <Html center transform sprite distanceFactor={18} style={{ pointerEvents: 'none' }}>
                        <div
                            style={{
                                padding: '3px 7px',
                                borderRadius: '999px',
                                background: 'rgba(15, 23, 42, 0.74)',
                                color: '#f8fafc',
                                border: '1px solid rgba(148, 163, 184, 0.28)',
                                fontSize: '11px',
                                fontWeight: 600,
                                whiteSpace: 'nowrap',
                                letterSpacing: '0.2px',
                                backdropFilter: 'blur(2px)',
                                boxShadow: '0 2px 6px rgba(2, 6, 23, 0.28)',
                            }}
                        >
                            {area.name}
                        </div>
                    </Html>
                </group>
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

export default function ThreeViewer({ model, isSimulated, onPointSelect, markers, damageOverlay, areaLabels }: {
    model: string | null,
    isSimulated?: boolean,
    onPointSelect?: (x: number, y: number, z: number) => void,
    markers?: {x: number, y: number, z: number, color: string}[],
    damageOverlay?: DamageOverlay,
    areaLabels?: AreaLabel[],
}) {
    return (
        <Canvas shadows dpr={[1, 2]} gl={{ antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}>
            <PerspectiveCamera makeDefault position={[12, 15, 15]} fov={50} />
            <OrbitControls
                makeDefault
                minPolarAngle={0}
                maxPolarAngle={Math.PI / 2.05}
                minDistance={4}
                maxDistance={75}
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
                        <Model url={model} useBuiltinMaterials={isSimulated} onPointSelect={onPointSelect} markers={markers} damageOverlay={damageOverlay} areaLabels={areaLabels} />
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
