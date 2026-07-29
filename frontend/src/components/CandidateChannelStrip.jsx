import React from 'react';

/**
 * CandidateChannelStrip Component
 * 
 * Renders a candidate as a horizontal mixing console channel strip with live VU/confidence meters.
 * Amber (`--tape`) for healthy confidence scores, alert coral (`--alert`) for `needs_review`.
 * 
 * Props:
 * - channelNumber: number | string (e.g. 1, "01")
 * - candidate: {
 *     id: string,
 *     name: string,
 *     role: string,
 *     stage: string,
 *     confidenceScore: number, // 0.0 to 1.0
 *     needsReview: boolean,
 *     timestamp: string,
 *     roomUrl?: string
 *   }
 * - onSelect: (candidateId: string) => void
 * - onJoinRoom?: (roomUrl: string) => void
 */
export default function CandidateChannelStrip({
  channelNumber = '01',
  candidate = null,
  onSelect,
  onJoinRoom
}) {
  if (!candidate) return null;

  const scorePercent = Math.min(Math.max((candidate.confidenceScore || 0) * 100, 0), 100);
  const isAlert = candidate.needsReview || scorePercent < 70;

  return (
    <div
      onClick={() => onSelect && onSelect(candidate.id)}
      className={`panel p-4 my-2 transition-all duration-200 cursor-pointer hover:border-[var(--tape)]/50 ${
        isAlert ? 'border-l-4 border-l-[var(--alert)]' : 'border-l-4 border-l-[var(--tape)]'
      }`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        
        {/* Channel Identifiers & Candidate Info */}
        <div className="flex items-start sm:items-center gap-3">
          <div className="font-mono text-xs text-[var(--mute)] bg-slate-900/80 px-2 py-1 rounded-[var(--radius)] border border-slate-800 shrink-0">
            CH-{String(channelNumber).padStart(2, '0')}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-body font-semibold text-[var(--bone)] text-base">
                {candidate.name}
              </span>
              <span className="font-mono text-[10px] uppercase px-2 py-0.5 rounded bg-[var(--panel)] text-[var(--mute)] border border-slate-800">
                {candidate.stage || 'SOURCING'}
              </span>
            </div>
            <div className="font-mono text-xs text-[var(--mute)] mt-0.5">
              ID: {candidate.id} • {candidate.role}
            </div>
          </div>
        </div>

        {/* Live Confidence Score Meter (Mixing Console VU Bar) */}
        <div className="flex-1 max-w-md space-y-1">
          <div className="flex justify-between items-center font-mono text-xs">
            <span className="text-[var(--mute)] uppercase tracking-wider text-[10px]">
              CONFIDENCE METER
            </span>
            <span
              className={`font-semibold ${
                isAlert ? 'text-[var(--alert)]' : 'text-[var(--tape)]'
              }`}
            >
              {(candidate.confidenceScore ?? 0).toFixed(2)} / 1.00
            </span>
          </div>

          {/* Meter Bar Container */}
          <div className="h-3 w-full bg-slate-950 rounded-[var(--radius)] overflow-hidden border border-slate-800 flex p-0.5 gap-0.5">
            {/* Array of VU meter LEDs */}
            {Array.from({ length: 20 }).map((_, idx) => {
              const threshold = (idx + 1) * 5;
              const isFilled = scorePercent >= threshold;
              return (
                <div
                  key={idx}
                  className={`h-full flex-1 rounded-[1px] transition-all duration-300 ${
                    isFilled
                      ? isAlert
                        ? 'bg-[var(--alert)] shadow-[0_0_4px_var(--alert)]'
                        : 'bg-[var(--tape)] shadow-[0_0_4px_var(--tape)]'
                      : 'bg-slate-900/60'
                  }`}
                />
              );
            })}
          </div>
        </div>

        {/* Console Switch Controls */}
        <div className="flex items-center gap-2 shrink-0">
          {candidate.roomUrl ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onJoinRoom) onJoinRoom(candidate.roomUrl);
                else window.open(candidate.roomUrl, '_blank');
              }}
              className="px-3 py-1.5 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-xs font-bold hover:bg-[#f3b04c] transition-all shadow-[0_0_10px_rgba(232,163,61,0.3)] flex items-center gap-1"
            >
              <span>●</span> LIVE ROOM
            </button>
          ) : (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onSelect) onSelect(candidate.id);
              }}
              className="px-3 py-1.5 rounded-[var(--radius)] bg-[var(--panel)] text-[var(--bone)] font-mono text-xs border border-slate-700 hover:border-[var(--tape)] transition-all"
            >
              INSPECT CHANNEL
            </button>
          )}

          {isAlert && (
            <span className="px-2 py-1 rounded bg-[var(--alert)]/20 text-[var(--alert)] font-mono text-[10px] border border-[var(--alert)]/50 uppercase tracking-wider font-semibold animate-pulse">
              NEEDS REVIEW
            </span>
          )}
        </div>

      </div>
    </div>
  );
}
