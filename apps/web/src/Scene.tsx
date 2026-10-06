import { Suspense, useEffect, useMemo } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { Edges, Environment, OrbitControls, OrthographicCamera, PerspectiveCamera, Stage, useGLTF } from '@react-three/drei'
import * as THREE from 'three'
import type { Feature } from './types'

function Part({ url, mode, features, selectedFeature, onSelect, onFeatureSelect }: { url: string; mode: string; features: Feature[]; selectedFeature: string; onSelect: () => void; onFeatureSelect: (id: string) => void }) {
  const { scene } = useGLTF(url)
  const clone = useMemo(() => scene.clone(true), [scene])
  clone.traverse((object) => {
    if (object instanceof THREE.Mesh) {
      object.castShadow = true
      object.receiveShadow = true
      const mats = Array.isArray(object.material) ? object.material : [object.material]
      for (const mat of mats) {
        if (mat instanceof THREE.MeshStandardMaterial) {
          mat.color.set(mode === 'translucent' ? '#d8e3ed' : '#aeb4bb')
          mat.metalness = .76
          mat.roughness = .28
          mat.transparent = mode === 'translucent'
          mat.opacity = mode === 'translucent' ? .38 : 1
        }
      }
    }
  })
  const center = useMemo(() => new THREE.Box3().setFromObject(clone).getCenter(new THREE.Vector3()), [clone])
  return <group rotation={[-Math.PI/2, 0, 0]} onClick={(e) => { e.stopPropagation(); onSelect() }}><group scale={0.01}><primitive object={clone} position={[-center.x, -center.y, -center.z]} />{features.filter((f) => f.id !== 'overall' && f.point_mm).map((feature) => { const point = feature.point_mm!; const active = feature.id === selectedFeature; return <mesh key={feature.id} position={[point[0]-center.x, point[1]-center.y, point[2]-center.z]} onClick={(e) => { e.stopPropagation(); onFeatureSelect(feature.id) }}><sphereGeometry args={[active ? 1.1 : .72, 16, 12]} /><meshStandardMaterial color={active ? '#86d3ae' : '#debd79'} emissive={active ? '#327455' : '#826a39'} emissiveIntensity={active ? .8 : .28} depthTest={false} /></mesh> })}</group>{mode === 'edges' && <Edges threshold={18} color="#e9eef4" scale={1.001} />}</group>
}

const PRESETS: Record<string, [number, number, number]> = { iso: [3, 2.4, 3.3], front: [0, 0, 3], back: [0, 0, -3], top: [0, 3, 0], bottom: [0, -3, 0], left: [-3, 0, 0], right: [3, 0, 0] }

function ViewController({ preset, frameScale, resetKey }: { preset: string; frameScale: number; resetKey: number }) {
  const camera = useThree((state) => state.camera)
  const controls = useThree((state) => state.controls) as (THREE.EventDispatcher & { target: THREE.Vector3; update: () => void }) | null
  useEffect(() => {
    const direction = PRESETS[preset] ?? PRESETS.iso
    camera.position.set(...direction.map((axis) => axis * frameScale) as [number, number, number])
    if (camera instanceof THREE.OrthographicCamera) {
      camera.zoom = 165 / frameScale
      camera.updateProjectionMatrix()
    }
    camera.up.set(0, 1, 0)
    camera.lookAt(0, 0, 0)
    controls?.target.set(0, 0, 0)
    controls?.update()
  }, [camera, controls, preset, frameScale, resetKey])
  return null
}

export function ModelCanvas({ url, mode, cameraKind, cameraPreset, boundsMm, resetKey, features = [], selectedFeature, onSelect, onFeatureSelect }: { url?: string; mode: string; cameraKind: string; cameraPreset: string; boundsMm?: Record<string, number>; resetKey: number; features?: Feature[]; selectedFeature: string; onSelect: () => void; onFeatureSelect: (id: string) => void }) {
  const modelSpan = boundsMm ? Math.max(boundsMm.x ?? 120, boundsMm.y ?? 70, boundsMm.z ?? 1.6) : 120
  const frameScale = Math.max(1, modelSpan / 120)
  return <Canvas dpr={[1, 2]} gl={{ antialias: true, alpha: false }} onPointerMissed={() => undefined}>
    <color attach="background" args={["#24272b"]} />
    <fog attach="fog" args={["#24272b", 8, 20]} />
    {cameraKind === 'perspective' ? <PerspectiveCamera makeDefault position={PRESETS.iso} fov={37} near={0.01} far={100} /> : <OrthographicCamera makeDefault position={PRESETS.iso} zoom={165 / frameScale} near={0.01} far={100} />}
    <ambientLight intensity={0.8} />
    <directionalLight position={[4, 7, 5]} intensity={3.1} />
    <directionalLight position={[-4, 2, -5]} intensity={1.2} color="#c7dcf3" />
    <Environment preset="studio" />
    <gridHelper args={[2, 40, '#53585e', '#383c41']} position={[0, -.03, 0]} />
    <axesHelper args={[0.18]} />
    <ViewController preset={cameraPreset} frameScale={frameScale} resetKey={resetKey} />
    <Suspense fallback={null}>{url ? <Stage intensity={.44} environment={null} shadows={false} adjustCamera={false}><Part key={url + mode} url={url} mode={mode} features={features} selectedFeature={selectedFeature} onSelect={onSelect} onFeatureSelect={onFeatureSelect} /></Stage> : <PlatePlaceholder onSelect={onSelect} />}</Suspense>
    <OrbitControls makeDefault enableDamping dampingFactor={.08} minDistance={.18} maxDistance={Math.max(12, frameScale * 7)} />
  </Canvas>
}

function PlatePlaceholder({ onSelect }: { onSelect: () => void }) {
  return <mesh position={[0, .01, 0]} rotation={[-Math.PI/2, 0, 0]} onClick={onSelect} castShadow receiveShadow>
    <boxGeometry args={[.12, .07, .003]} /><meshStandardMaterial color="#aeb4bb" metalness={.74} roughness={.3} /><Edges threshold={18} color="#f1f4f7" />
  </mesh>
}
