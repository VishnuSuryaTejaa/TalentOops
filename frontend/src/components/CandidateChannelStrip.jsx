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
      className={`panel p-4 my-2 transition-all duration-200 cursor-pointer hover:border-[rgba(204,255,0,0.5)] ${
        isAlert ? 'border-l-4 border-l-[var(--alert)]' : 'border-l-4 border-l-[var(--tape)]'
      }`}
    >
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 lg:gap-6 w-full">
        
        {/* Channel Identifiers & Candidate Info */}
        <div className="flex items-start sm:items-center gap-3 lg:w-1/3 w-full">
          <div className="font-mono text-xs text-[var(--mute)] bg-black/40 px-2 py-1 rounded-[var(--radius)] border border-[rgba(255,255,255,0.05)] shrink-0">
            CH-{String(channelNumber).padStart(2, '0')}
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-display font-semibold text-[var(--bone)] text-base truncate">
                {candidate.name}
              </span>
              <span className="font-mono text-xs uppercase px-2 py-0.5 rounded bg-black/30 text-[var(--mute)] border border-[rgba(255,255,255,0.1)] shrink-0">
                {candidate.stage || 'SOURCING'}
              </span>
            </div>
            <div className="font-mono text-xs text-[rgba(255,255,255,0.5)] mt-0.5 truncate">
              ID: {candidate.id} • {candidate.role}
            </div>
          </div>
        </div>

        {/* Live Confidence Score Meter (Mixing Console VU Bar) */}
        <div className="flex-1 w-full lg:max-w-md space-y-1">
          <div className="flex justify-between items-center font-mono text-xs mb-1">
            <span className="text-[var(--mute)] uppercase tracking-wider text-xs">
              CONFIDENCE METER
            </span>
            <span
              className={`font-semibold ${
                isAlert ? 'text-[var(--alert)] drop-shadow-[0_0_4px_rgba(255,107,91,0.5)]' : 'text-[var(--tape)] drop-shadow-[0_0_4px_rgba(204,255,0,0.5)]'
              }`}
            >
              {(candidate.confidenceScore ?? 0).toFixed(2)} / 1.00
            </span>
          </div>

          {/* Meter Bar Container */}
          <div className="h-3.5 w-full bg-black/50 rounded-[var(--radius)] overflow-hidden border border-[rgba(255,255,255,0.05)] flex p-[3px] gap-[3px]">
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
                        ? 'bg-[var(--alert)] shadow-[0_0_8px_var(--alert)]'
                        : 'bg-[var(--tape)] shadow-[0_0_8px_var(--tape)]'
                      : 'bg-[rgba(255,255,255,0.1)]'
                  }`}
                />
              );
            })}
          </div>
        </div>

        {/* Console Switch Controls */}
        <div className="flex items-center gap-2 shrink-0 lg:justify-end mt-2 lg:mt-0">
          {candidate.roomUrl ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onJoinRoom) onJoinRoom(candidate.roomUrl);
                else window.open(candidate.roomUrl, '_blank');
              }}
              className="px-4 py-2 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-xs sm:text-sm font-bold hover:bg-[#e6ff00] transition-all shadow-[0_0_15px_rgba(204,255,0,0.4)] flex items-center gap-1.5"
            >
              <span className="animate-pulse">●</span> LIVE ROOM
            </button>
          ) : (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (onSelect) onSelect(candidate.id);
              }}
              className="px-4 py-2 rounded-[var(--radius)] bg-[rgba(255,255,255,0.05)] text-[var(--bone)] font-mono text-xs sm:text-sm border border-[rgba(255,255,255,0.1)] hover:border-[var(--tape)] hover:bg-[rgba(204,255,0,0.1)] transition-all"
            >
              INSPECT CHANNEL
            </button>
          )}

          {isAlert && (
            <span className="px-2 py-2 rounded bg-[var(--alert)]/20 text-[var(--alert)] font-mono text-xs border border-[var(--alert)]/50 uppercase tracking-wider font-semibold animate-pulse shadow-[0_0_10px_rgba(255,107,91,0.2)]">
              REVIEW
            </span>
          )}
        </div>

      </div>
    </div>
  );
}
