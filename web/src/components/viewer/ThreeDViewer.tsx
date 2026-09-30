import React, { useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Html } from '@react-three/drei';
import { useCardioStore } from '../../store/useCardioStore';
import { riskColor } from '../../lib/colorScale';

interface ThreeDViewerProps {
  selectedVessel: string | null;
}

const CoronaryVessel = ({
  name,
  position,
  rotation,
  isSelected,
  probability,
  onSelect
}: {
  name: string;
  position: [number, number, number];
  rotation: [number, number, number];
  isSelected: boolean;
  probability: number | undefined;
  onSelect: (name: string) => void;
}) => {
  const color = probability === undefined ? '#64748b' : riskColor(probability);

  return (
    <group position={position} rotation={rotation}>
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          onSelect(name);
        }}
        scale={isSelected ? [1.3, 1.1, 1.3] : [1, 1, 1]}
      >
        <cylinderGeometry args={[0.08, 0.06, 1.2, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={isSelected ? '#ffffff' : '#000000'}
          emissiveIntensity={isSelected ? 0.2 : 0.0}
          roughness={0.3}
          metalness={0.1}
        />
      </mesh>
      <Html position={[0, 0.7, 0]} center distanceFactor={8}>
        <div
          onClick={(e) => {
            e.stopPropagation();
            onSelect(name);
          }}
          className={`px-2 py-0.5 text-xs font-semibold rounded shadow cursor-pointer transition-all select-none ${
            isSelected
              ? 'bg-blue-600 text-white ring-2 ring-white scale-110'
              : 'bg-white/90 text-gray-800 hover:bg-white'
          }`}
        >
          {name}
          {probability !== undefined && (
            <span className="ml-1 text-[10px] opacity-80">
              ({(probability * 100).toFixed(0)}%)
            </span>
          )}
        </div>
      </Html>
    </group>
  );
};

const ThreeDViewer: React.FC<ThreeDViewerProps> = ({ selectedVessel }) => {
  const { prediction, setSelectedVessel } = useCardioStore();

  const vesselPositions: Record<string, { pos: [number, number, number]; rot: [number, number, number] }> = {
    LAD: { pos: [-0.3, 0.3, 0.7], rot: [0.3, 0, -0.4] }, // Anterior
    LCX: { pos: [0.6, 0.4, 0.2], rot: [0.1, 0.6, 0.5] }, // Circumflex / lateral
    RCA: { pos: [-0.6, 0.2, 0.1], rot: [0.2, -0.5, -0.6] } // Right side
  };

  return (
    <div className="relative h-96 w-full rounded-xl shadow-lg bg-gradient-to-b from-slate-900 to-slate-950 overflow-hidden border border-slate-800">
      {/* Top Overlay Header */}
      <div className="absolute top-3 left-3 z-10 bg-slate-900/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-slate-700 text-xs text-slate-200">
        <span className="font-semibold text-white">Interactive 3D Heart & Coronary Tree</span>
        <div className="text-[10px] text-slate-400">Click a vessel or rotate/zoom camera</div>
      </div>

      {/* Risk Legend */}
      <div className="absolute bottom-3 left-3 z-10 bg-slate-900/80 backdrop-blur-md px-3 py-2 rounded-lg border border-slate-700 text-[11px] text-slate-300 flex items-center gap-3">
        <span className="font-semibold text-slate-400">Estimated stenosis:</span>
        <span>0% <span className="inline-block align-middle w-24 h-2 rounded" style={{ background: 'linear-gradient(to right, #10b981, #f59e0b, #ef4444)' }} /> 100%</span>
        <span>Selected vessel is enlarged</span>
      </div>

      <Canvas camera={{ position: [0, 1, 4], fov: 45 }}>
        {/* Lights */}
        <ambientLight intensity={0.7} />
        <directionalLight position={[10, 15, 10]} intensity={1.2} />
        <pointLight position={[-10, -10, -10]} intensity={0.4} color="#60a5fa" />

        {/* Anatomical Torso Silhouette (translucent) */}
        <mesh position={[0, -0.2, -0.2]}>
          <cylinderGeometry args={[1.5, 1.2, 3.2, 32]} />
          <meshStandardMaterial
            color="#334155"
            opacity={0.18}
            transparent
            roughness={0.8}
            wireframe={false}
          />
        </mesh>

        {/* Cardiac Base (Heart Body) */}
        <group position={[0, 0.3, 0]}>
          {/* Main myocardium shape */}
          <mesh scale={[0.85, 1.1, 0.85]} rotation={[0.1, 0.2, -0.15]}>
            <sphereGeometry args={[0.9, 32, 32]} />
            <meshStandardMaterial
              color="#be123c"
              roughness={0.4}
              metalness={0.1}
            />
          </mesh>

          {/* Aorta arch atop heart */}
          <mesh position={[0.05, 0.95, -0.1]} rotation={[0, 0, Math.PI / 4]}>
            <torusGeometry args={[0.3, 0.12, 16, 32, Math.PI]} />
            <meshStandardMaterial color="#dc2626" roughness={0.3} />
          </mesh>

          {/* Coronary Vessels */}
          {(['LAD', 'LCX', 'RCA'] as const).map((vessel) => {
            const prob = prediction?.[vessel]?.probability;
            const isSelected = selectedVessel === vessel;
            const cfg = vesselPositions[vessel];
            return (
              <CoronaryVessel
                key={vessel}
                name={vessel}
                position={cfg.pos}
                rotation={cfg.rot}
                isSelected={isSelected}
                probability={prob}
                onSelect={(name) => setSelectedVessel(selectedVessel === name ? null : name)}
              />
            );
          })}
        </group>

        {/* Camera Controls */}
        <OrbitControls
          enableZoom={true}
          enablePan={true}
          enableRotate={true}
          minDistance={2}
          maxDistance={8}
          autoRotate={false}
        />
      </Canvas>
    </div>
  );
};

export default ThreeDViewer;
