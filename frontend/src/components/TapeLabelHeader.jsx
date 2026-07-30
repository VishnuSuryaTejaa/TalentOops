import React from 'react';

/**
 * TapeLabelHeader Component
 * 
 * Renders the pipeline run metadata (goal, evaluation standard, started timestamp)
 * styled as a tape label in IBM Plex Mono.
 * 
 * Props:
 * - goal: string
 * - standard: string
 * - runId: string
 * - timestamp: string
 */
export default function TapeLabelHeader({
  goal = 'Hire Senior Backend Engineer',
  standard = 'Must demonstrate strong async Python and SQL optimization skills',
  runId = 'run-8000',
  timestamp = new Date().toISOString()
}) {
  return (
    <div className="panel bg-[rgba(21,26,36,0.6)] border border-dashed border-[rgba(255,255,255,0.1)] p-4 rounded-[var(--radius)] font-mono text-xs text-[var(--bone)] shadow-sm max-w-full lg:max-w-xl w-full">
      <div className="flex flex-wrap items-center justify-between border-b border-[rgba(255,255,255,0.05)] pb-2 mb-3 text-[10px] text-[var(--mute)] uppercase tracking-wider gap-2">
        <span className="flex items-center gap-1.5 text-[var(--tape)]">
          <span className="w-2 h-2 bg-[var(--tape)] rounded-full inline-block animate-pulse" />
          TAPE REEL METADATA // REC-800
        </span>
        <span className="bg-black/30 px-2 py-0.5 rounded">ID: {runId}</span>
      </div>

      <div className="space-y-2">
        <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
          <span className="text-[var(--mute)] uppercase text-[10px] w-16 shrink-0">GOAL:</span>
          <span className="font-semibold text-[var(--bone)]">{goal}</span>
        </div>
        <div className="flex flex-col sm:flex-row sm:items-baseline gap-1 sm:gap-2">
          <span className="text-[var(--mute)] uppercase text-[10px] w-16 shrink-0">STANDARD:</span>
          <span className="text-[rgba(255,255,255,0.7)]">{standard}</span>
        </div>
        <div className="text-[10px] text-[rgba(255,255,255,0.4)] pt-2 mt-2 border-t border-[rgba(255,255,255,0.05)] flex flex-wrap justify-between gap-2">
          <span>STARTED: {timestamp}</span>
          <span className="text-[var(--signal)]">AUDIO_CAPTURE: ENABLED</span>
        </div>
      </div>
    </div>
  );
}
