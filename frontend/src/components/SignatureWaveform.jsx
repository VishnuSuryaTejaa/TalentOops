import React, { useState, useEffect } from 'react';

/**
 * SignatureWaveform Component
 * 
 * The signature visual element of TalentOps:
 * - On the live interview room screen: real-time amber (--tape) waveform.
 * - On the HR Debrief room screen: cool cyan (--signal) waveform.
 * - As speech is transcribed, waveform bars nearest the playhead morph directly into
 *   IBM Plex Mono glyphs/words of the transcript (Waveform -> Transcript dissolve).
 * 
 * Props:
 * - active: boolean
 * - variant: 'tape' | 'signal'
 * - barCount: number (default 40)
 * - liveText: string (latest spoken text dissolving from audio into transcript)
 * - caption: string
 * - className: string
 */
export default function SignatureWaveform({
  active = false,
  variant = 'tape',
  barCount = 36,
  liveText = '',
  caption,
  className = ''
}) {
  const isSignal = variant === 'signal';
  const accentHex = isSignal ? '#5FD3C4' : '#E8A33D';
  const accentClass = isSignal ? 'text-[var(--signal)]' : 'text-[var(--tape)]';
  const bgAccentClass = isSignal ? 'bg-[var(--signal)]' : 'bg-[var(--tape)]';

  // Dissolve animation state: mock words dissolving near playhead
  const [dissolvingWords, setDissolvingWords] = useState([]);

  useEffect(() => {
    if (active && liveText) {
      const words = liveText.trim().split(/\s+/).slice(-4);
      setDissolvingWords(words);
    } else {
      setDissolvingWords([]);
    }
  }, [active, liveText]);

  return (
    <div className={`w-full panel p-3 bg-slate-950/90 border-slate-800 space-y-2 select-none ${className}`}>
      
      {/* Top Meta Bar */}
      <div className="flex items-center justify-between font-mono text-[10px] uppercase text-[var(--mute)] px-1">
        <div className="flex items-center gap-2">
          <span
            className={`w-2 h-2 rounded-full inline-block ${
              active ? `${bgAccentClass} animate-signal-pulse` : 'bg-slate-700'
            }`}
          />
          <span className={active ? `${accentClass} font-semibold` : ''}>
            {caption || (isSignal ? 'SIGNAL // HR DEBRIEF VOICE CHANNEL' : 'SIGNAL // CANDIDATE AUDIO CHANNEL')}
          </span>
        </div>
        <div>
          AUDIO STT // <span className="text-[var(--bone)]">48.0kHz 16-bit</span>
        </div>
      </div>

      {/* Waveform Bar + Dissolve Area */}
      <div className="relative flex items-center justify-between gap-1 h-14 px-3 bg-[#0B0E14] rounded-[var(--radius)] border border-slate-800/80 overflow-hidden">
        
        {/* Playhead Indicator Line */}
        <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-[var(--tape)]/60 z-10 animate-pulse pointer-events-none" />

        {/* Waveform LED Bars */}
        <div className="flex-1 flex items-center justify-center gap-1 h-full py-1">
          {Array.from({ length: barCount }).map((_, idx) => {
            const centerOffset = Math.abs(idx - barCount / 2);
            const amplitude = Math.sin((idx + Date.now() * 0.003) * 0.5) * 0.4 + 0.5;
            const barHeight = active ? Math.max(15, Math.min(100, amplitude * 100 - centerOffset * 1.5)) : 20;

            return (
              <div
                key={idx}
                className={`w-1 rounded-full transition-all duration-150 ${bgAccentClass} ${
                  active ? 'opacity-90' : 'opacity-25'
                }`}
                style={{
                  height: `${barHeight}%`,
                  boxShadow: active ? `0 0 6px ${accentHex}` : 'none'
                }}
              />
            );
          })}
        </div>

        {/* Dissolve Text Overlay (Audio -> IBM Plex Mono Glyphs) */}
        {active && dissolvingWords.length > 0 && (
          <div className="absolute left-1/2 top-0 bottom-0 right-0 pl-3 font-mono text-sm font-bold pointer-events-none flex items-center bg-gradient-to-r from-[var(--ink)]/0 via-[var(--ink)]/90 to-[var(--ink)]">
            <span 
              className={`${accentClass} tracking-widest animate-pulse mix-blend-screen`} 
              style={{ textShadow: `0 0 12px ${accentHex}` }}
            >
              {dissolvingWords.join(' ')}
            </span>
          </div>
        )}

      </div>
    </div>
  );
}
