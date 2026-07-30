import React from 'react';

export default function LiquidGradientBackground() {
  return (
    <div className="fixed inset-0 z-0 overflow-hidden bg-ink pointer-events-none">
      
      {/* Liquid gradients container */}
      <div className="absolute inset-0 w-full h-full opacity-60">
        <div className="absolute top-[-10%] left-[-10%] w-[60vw] h-[60vw] bg-signal rounded-full mix-blend-screen filter blur-[140px] animate-blob" />
        <div className="absolute top-[10%] right-[-10%] w-[50vw] h-[50vw] bg-tape rounded-full mix-blend-screen filter blur-[140px] animate-blob animation-delay-2000" />
        <div className="absolute bottom-[-20%] left-[10%] w-[70vw] h-[70vw] bg-[#4c1d95] rounded-full mix-blend-screen filter blur-[160px] animate-blob animation-delay-4000" />
        <div className="absolute top-[30%] left-[30%] w-[60vw] h-[60vw] bg-[#0369a1] rounded-full mix-blend-screen filter blur-[140px] animate-blob animation-delay-6000" />
      </div>

      {/* Subtle Noise texture overlay for premium, non-banding feel */}
      <div 
        className="absolute inset-0 opacity-[0.04] mix-blend-overlay z-0" 
        style={{ 
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.8%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")' 
        }} 
      />

      {/* Heavy Glass overlay for smooth light dispersion */}
      <div className="absolute inset-0 bg-ink/60 backdrop-blur-[50px] z-10" />
    </div>
  );
}
