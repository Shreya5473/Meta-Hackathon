import { useStore } from '@/shared/state/store'
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Stars, Environment } from '@react-three/drei'
import { Bloom, EffectComposer, Vignette } from '@react-three/postprocessing'
import { Suspense, useMemo, useRef } from 'react'
import * as THREE from 'three'
import { useFrame } from '@react-three/fiber'

export function VisualizationCanvas({ signals, gti }: { signals: any[], gti: any }) {
    const { mode } = useStore()

    return (
        <div className="w-full h-full bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-[#1e293b] via-[#0f172a] to-[#010616]">
            <Canvas camera={{ position: [0, 0, 15], fov: 45 }}>
                <color attach="background" args={(['#010616'] as any)} />
                <ambientLight intensity={0.2} />
                <pointLight position={[10, 10, 10]} intensity={1.5} color="#ffffff" />
                <Suspense fallback={null}>
                    {mode === 'globe' && <EarthMode />}
                    {(mode as string) === 'quantum' && <QuantumMode signals={signals} gti={gti} />}
                    {(mode as string) === 'attractor' && <AttractorMode signals={signals} gti={gti} />}
                    <Environment preset="city" />
                </Suspense>

                <EffectComposer>
                    <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} intensity={1.5} mipmapBlur />
                    <Vignette eskil={false} offset={0.1} darkness={1.1} />
                </EffectComposer>

                <OrbitControls enablePan={true} enableZoom={true} enableRotate={true} />
                <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />
            </Canvas>
        </div>
    )
}

function EarthMode() {
    const meshRef = useRef<THREE.Mesh>(null)

    useFrame(() => {
        if (meshRef.current) {
            meshRef.current.rotation.y += 0.002
        }
    })

    // Simple wireframe sphere as placeholder for MVP Earth pulse
    return (
        <group>
            <mesh ref={meshRef}>
                <sphereGeometry args={[5, 64, 64]} />
                <meshStandardMaterial color="#000000" metalness={0.9} roughness={0.1} />
            </mesh>

            {/* Wireframe overlay */}
            <mesh ref={meshRef as any}>
                <sphereGeometry args={[5.05, 32, 32]} />
                <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.1} />
            </mesh>

            {/* Glow */}
            <mesh>
                <sphereGeometry args={[5.2, 32, 32]} />
                <meshBasicMaterial color="#ffffff" transparent opacity={0.05} blending={THREE.AdditiveBlending} />
            </mesh>
        </group>
    )
}

function QuantumMode({ signals, gti }: { signals: any[], gti: any }) {
    const count = signals.length || 100
    const meshRef = useRef<THREE.InstancedMesh>(null)

    // Use useMemo to prevent recreating positions every render
    const dummy = useMemo(() => new THREE.Object3D(), [])
    const colors = useMemo(() => new Float32Array(count * 3), [count])

    useFrame((state) => {
        if (!meshRef.current) return
        const time = state.clock.getElapsedTime()
        const tensionMult = gti?.gti_value ? (gti.gti_value / 50) : 1.0

        for (let i = 0; i < count; i++) {
            const signal = signals[i]
            const angle = (i / count) * Math.PI * 2
            const radius = 6 + Math.sin(time * 0.5 * tensionMult + i) * 2 // tension impacts movement

            const x = Math.cos(angle) * radius
            const y = Math.sin(time + i) * 3
            const z = Math.sin(angle) * radius

            dummy.position.set(x, y, z)
            dummy.rotation.x = time * 0.2
            dummy.rotation.y = time * 0.2
            dummy.updateMatrix()
            meshRef.current.setMatrixAt(i, dummy.matrix)

            // Compute color
            const color = new THREE.Color()
            if (signal?.recommendation === "BUY") color.set("#22c55e")
            else if (signal?.recommendation === "SELL") color.set("#ef4444")
            else color.set("#f59e0b")

            color.toArray(colors, i * 3)
        }
        meshRef.current.instanceMatrix.needsUpdate = true
        if (meshRef.current.instanceColor) {
            meshRef.current.instanceColor.needsUpdate = true
        }
    })

    // Set colors on initialization
    useMemo(() => {
        for (let i = 0; i < count; i++) {
            const signal = signals[i]
            const color = new THREE.Color()
            if (signal?.recommendation === "BUY") color.set("#22c55e")
            else if (signal?.recommendation === "SELL") color.set("#ef4444")
            else color.set("#ffffff")
            color.toArray(colors, i * 3)
        }
    }, [count, signals, colors])

    return (
        <instancedMesh ref={meshRef} args={[undefined, undefined, count]} castShadow>
            <dodecahedronGeometry args={[0.2, 0]} />
            <meshStandardMaterial metalness={0.8} roughness={0.2} toneMapped={false}>
                <instancedBufferAttribute attach="instanceColor" args={[colors, 3]} />
            </meshStandardMaterial>
        </instancedMesh>
    )
}

function AttractorMode({ signals, gti }: { signals: any[], gti: any }) {
    const count = signals.length || 100
    const meshRef = useRef<THREE.InstancedMesh>(null)
    const dummy = useMemo(() => new THREE.Object3D(), [])
    const colors = useMemo(() => new Float32Array(count * 3), [count])

    useFrame((state) => {
        if (!meshRef.current) return
        const time = state.clock.getElapsedTime()
        const tensionMult = gti?.gti_value ? (gti.gti_value / 50) : 1.0

        for (let i = 0; i < count; i++) {
            // Strange attractor math placeholder
            const t = time * 0.2 * tensionMult + i * 0.1
            const x = Math.sin(t * 2.1) * Math.cos(t * 1.5) * 8
            const y = Math.sin(t * 1.3) * Math.cos(t * 2.5) * 8
            const z = Math.sin(t * 1.8) * Math.cos(t * 1.1) * 8

            dummy.position.set(x, y, z)
            dummy.scale.setScalar(0.5 + Math.sin(time * 5 + i) * 0.2)
            dummy.updateMatrix()
            meshRef.current.setMatrixAt(i, dummy.matrix)

            const signal = signals[i]
            const color = new THREE.Color()
            if (signal?.recommendation === "BUY") color.set("#22c55e")
            else if (signal?.recommendation === "SELL") color.set("#ef4444")
            else color.set("#f59e0b")

            color.toArray(colors, i * 3)
        }
        meshRef.current.instanceMatrix.needsUpdate = true
        if (meshRef.current.instanceColor) {
            meshRef.current.instanceColor.needsUpdate = true
        }
    })

    useMemo(() => {
        for (let i = 0; i < count; i++) {
            const signal = signals[i]
            const color = new THREE.Color()
            if (signal?.recommendation === "BUY") color.set("#22c55e")
            else if (signal?.recommendation === "SELL") color.set("#ef4444")
            else color.set("#ffffff")
            color.toArray(colors, i * 3)
        }
    }, [count, signals, colors])

    return (
        <instancedMesh ref={meshRef} args={[undefined, undefined, count]} castShadow>
            <octahedronGeometry args={[0.2, 0]} />
            <meshStandardMaterial metalness={0.8} roughness={0.2} toneMapped={false}>
                <instancedBufferAttribute attach="instanceColor" args={[colors, 3]} />
            </meshStandardMaterial>
        </instancedMesh>
    )
}
