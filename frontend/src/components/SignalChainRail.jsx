import React from 'react';

export const SIGNAL_STAGES = [
  { id: 'sourcing', label: 'SOURCING' },
  { id: 'screening', label: 'SCREENING' },
  { id: 'scheduling', label: 'SCHEDULING' },
  { id: 'interview', label: 'INTERVIEW' },
  { id: 'eval', label: 'EVAL' },
  { id: 'debrief', label: 'DEBRIEF' }
];

/**
 * SignalChainRail Component
 * 
 * The persistent horizontal signal path matching "The Signal Chain" design thesis.
 * Features a thin conductive line with a 2.4s slow amber pulse carrying current to the active stage node.
 * 
 * Props:
 * - activeStage: string ('sourcing' | 'screening' | 'scheduling' | 'interview' | 'eval' | 'debrief')
 * - completedStages: Array<string>
 * - onStageSelect: (stageId: string) => void
 * - runTitle: string
 * - isLive: boolean
 */
export default function SignalChainRail({
  activeStage = 'sourcing',
  completedStages = [],
  onStageSelect,
  runTitle = 'Hire Senior Engineer',
  isLive = false
}) {
  const activeIndex = SIGNAL_STAGES.findIndex(s => s.id === activeStage);

  return (
    <header className="sticky top-0 z-50 w-full bg-[var(--ink)]/95 backdrop-blur border-b border-slate-800/80 px-4 py-3 select-none">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-3">
        
        {/* Brand & Run Label */}
        <div className="flex items-center gap-3">
          <div className="font-display font-extrabold text-lg tracking-tight text-[var(--bone)] flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[var(--tape)] inline-block animate-signal-pulse" />
            TALENT<span className="text-[var(--tape)]">OPS</span>
          </div>
          <span className="text-slate-700 font-mono text-xs">|</span>
          <div className="font-mono text-xs text-[var(--mute)] truncate max-w-[240px] sm:max-w-xs">
            <span className="text-slate-500 uppercase">RUN:</span>{' '}
            <span className="text-[var(--bone)]">{runTitle}</span>
          </div>
        </div>

        {/* The Signal Chain Rail */}
        <nav className="flex items-center gap-1 sm:gap-2 overflow-x-auto py-1 scrollbar-none">
          {SIGNAL_STAGES.map((stage, idx) => {
            const isActive = stage.id === activeStage;
            const isCompleted = completedStages.includes(stage.id) || idx < activeIndex;
            const isNextToActive = idx === activeIndex;

            return (
              <React.Fragment key={stage.id}>
                {/* Conductive Line connecting previous node */}
                {idx > 0 && (
                  <div className="flex-1 min-w-[20px] sm:min-w-[36px] h-[2px] relative bg-slate-800 rounded">
                    {/* Active current flow or completed line */}
                    <div
                      className={`h-full transition-all duration-300 ${
                        idx <= activeIndex
                          ? idx === activeIndex
                            ? 'bg-[var(--tape)] animate-signal-pulse shadow-[0_0_8px_rgba(204,255,0,0.6)]'
                            : 'bg-[var(--tape)]/50'
                          : 'bg-slate-800'
                      }`}
                      style={{
                        width: idx <= activeIndex ? '100%' : '0%'
                      }}
                    />
                  </div>
                )}

                {/* Stage Node */}
                <button
                  type="button"
                  onClick={() => onStageSelect && onStageSelect(stage.id)}
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-[var(--radius)] font-mono text-xs transition-all duration-200 ${
                    isActive
                      ? 'bg-[var(--panel)] text-[var(--tape)] border border-[var(--tape)]/60 shadow-[0_0_12px_rgba(204,255,0,0.25)] font-semibold'
                      : isCompleted
                      ? 'text-[var(--bone)] hover:text-white border border-transparent hover:border-slate-800'
                      : 'text-[var(--mute)] opacity-50 hover:opacity-80 border border-transparent'
                  }`}
                >
                  {/* Node Dot indicator */}
                  <span
                    className={`w-2 h-2 rounded-full inline-block ${
                      isActive
                        ? 'bg-[var(--tape)] animate-signal-pulse shadow-[0_0_8px_rgba(204,255,0,0.8)]'
                        : isCompleted
                        ? 'bg-[var(--tape)]/50'
                        : 'bg-slate-700'
                    }`}
                  />
                  <span className="tracking-wider">{stage.label}</span>
                </button>
              </React.Fragment>
            );
          })}
        </nav>

        {/* Live Status indicator */}
        <div className="hidden lg:flex items-center gap-2 font-mono text-xs">
          <span className="text-[var(--mute)]">SIGNAL:</span>
          {isLive ? (
            <span className="px-2 py-0.5 rounded bg-[var(--tape)]/15 text-[var(--tape)] border border-[var(--tape)]/40 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--tape)] animate-ping" />
              LIVE DEEP SEARCH
            </span>
          ) : (
            <span className="px-2 py-0.5 rounded bg-slate-900 text-slate-400 border border-slate-800">
              STANDBY
            </span>
          )}
        </div>
      </div>
    </header>
  );
}
