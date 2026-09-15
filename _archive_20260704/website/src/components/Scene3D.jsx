import { Canvas, useFrame } from '@react-three/fiber';
import { Float, MeshDistortMaterial, Sparkles, Torus } from '@react-three/drei';
import { useRef, Suspense } from 'react';

// The luminous, breathing core — an encrypted "vault" orb.
function Core() {
  const mesh = useRef();
  useFrame((state) => {
    if (mesh.current) {
      mesh.current.rotation.y = state.clock.elapsedTime * 0.18;
      mesh.current.rotation.x = state.clock.elapsedTime * 0.08;
    }
  });
  return (
    <Float speed={1.4} rotationIntensity={0.6} floatIntensity={1.4}>
      <mesh ref={mesh} scale={1.9}>
        <icosahedronGeometry args={[1, 16]} />
        <MeshDistortMaterial
          color="#0ea5a4"
          emissive="#0ea5a4"
          emissiveIntensity={0.45}
          roughness={0.12}
          metalness={0.65}
          distort={0.34}
          speed={2.1}
        />
      </mesh>
    </Float>
  );
}

// Orbiting glassy coins/rings.
function Coin({ radius, speed, y, color, scale }) {
  const ref = useRef();
  useFrame((state) => {
    const t = state.clock.elapsedTime * speed;
    if (ref.current) {
      ref.current.position.x = Math.cos(t) * radius;
      ref.current.position.z = Math.sin(t) * radius;
      ref.current.position.y = y + Math.sin(t * 1.6) * 0.25;
      ref.current.rotation.x = t * 0.8;
      ref.current.rotation.y = t * 0.6;
    }
  });
  return (
    <Float speed={2} floatIntensity={0.6}>
      <Torus ref={ref} args={[0.32, 0.13, 24, 64]} scale={scale}>
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={0.5}
          metalness={0.8}
          roughness={0.2}
        />
      </Torus>
    </Float>
  );
}

export default function Scene3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 6], fov: 42 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <Suspense fallback={null}>
        <ambientLight intensity={0.45} />
        <directionalLight position={[5, 6, 5]} intensity={1.3} />
        <pointLight position={[-6, -3, 2]} color="#34d399" intensity={6} />
        <pointLight position={[4, -2, -4]} color="#0ea5a4" intensity={4} />
        <Core />
        <Coin radius={3.1} speed={0.5} y={0.6} color="#5eead4" scale={1} />
        <Coin radius={2.6} speed={-0.7} y={-0.8} color="#34d399" scale={0.8} />
        <Coin radius={3.5} speed={0.35} y={-0.2} color="#a7f3d0" scale={0.6} />
        <Sparkles count={70} scale={11} size={2.4} speed={0.4} color="#5eead4" opacity={0.7} />
      </Suspense>
    </Canvas>
  );
}
