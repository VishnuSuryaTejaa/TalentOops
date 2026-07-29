import React from 'react';

/**
 * TranscriptBlock Component
 * 
 * Renders system logs, transcript lines, machine evidence, or raw JSON data
 * using IBM Plex Mono in the Control Room aesthetic.
 * 
 * Props:
 * - speaker: string (e.g. "OralInterviewAgent", "CANDIDATE", "SYSTEM")
 * - timestamp: string (e.g. "14:23:02.108")
 * - isEvidence: boolean (if true, adds a thin cyan border-left marking machine evidence)
 * - children: ReactNode
 * - className: string
 */
export default function TranscriptBlock({
  speaker,
  timestamp,
  isEvidence = false,
  children,
  className = ''
}) {
  return (
    <div
      className={`font-mono text-sm p-3 my-2 bg-[var(--panel)] rounded-[var(--radius)] border ${
        isEvidence
          ? 'border-l-2 border-[var(--signal)] border-t-slate-800 border-r-slate-800 border-b-slate-800'
          : 'border-slate-800/60'
      } text-[var(--bone)] ${className}`}
      style={{ letterSpacing: '0.01em' }}
    >
      {(speaker || timestamp) && (
        <div className="flex items-center justify-between text-xs text-[var(--mute)] mb-1.5 uppercase font-medium tracking-wider select-none">
          {speaker && (
            <span className={isEvidence ? 'text-[var(--signal)]' : 'text-[var(--tape)]'}>
              [{speaker}]
            </span>
          )}
          {timestamp && <span>{timestamp}</span>}
        </div>
      )}
      <div className="leading-relaxed whitespace-pre-wrap break-words">
        {children}
      </div>
    </div>
  );
}
