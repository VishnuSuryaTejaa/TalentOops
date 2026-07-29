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
    <div className="bg-[#121620] border border-dashed border-slate-700/80 p-3 rounded-[var(--radius)] font-mono text-xs text-[var(--bone)] shadow-sm max-w-xl">
      <div className="flex items-center justify-between border-b border-slate-800 pb-1.5 mb-2 text-[10px] text-[var(--mute)] uppercase tracking-wider">
        <span className="flex items-center gap-1.5 text-[var(--tape)]">
          <span className="w-2 h-2 bg-[var(--tape)] rounded-full inline-block" />
          TAPE REEL METADATA // REC-800
        </span>
        <span>ID: {runId}</span>
      </div>

      <div className="space-y-1">
        <div>
          <span className="text-[var(--mute)] uppercase text-[10px]">GOAL:</span>{' '}
          <span className="font-medium text-[var(--bone)]">{goal}</span>
        </div>
        <div>
          <span className="text-[var(--mute)] uppercase text-[10px]">STANDARD:</span>{' '}
          <span className="text-slate-300">{standard}</span>
        </div>
        <div className="text-[10px] text-slate-500 pt-1 flex justify-between">
          <span>STARTED: {timestamp}</span>
          <span className="text-[var(--signal)]">AUDIO_CAPTURE: ENABLED</span>
        </div>
      </div>
    </div>
  );
}
