import React from 'react';

export const SIGNAL_STAGES = [
  { id: 'sourcing', label: 'SOURCING', icon: '🔍' },
  { id: 'screening', label: 'SCREENING', icon: '📝' },
  { id: 'scheduling', label: 'SCHEDULING', icon: '📅' },
  { id: 'interview', label: 'INTERVIEW', icon: '🎙️' },
  { id: 'eval', label: 'EVAL & DEBRIEF', icon: '🧠' },
  { id: 'scorecard', label: 'SCORECARD', icon: '📊' }
];

export default function SidebarNavigation({
  activeStage = 'sourcing',
  completedStages = [],
  onStageSelect,
  runTitle = 'Hire Senior Engineer',
  isLive = false
}) {
  const activeIndex = SIGNAL_STAGES.findIndex(s => s.id === activeStage);

  return (
    <aside className="w-64 lg:w-72 border-r border-[rgba(255,255,255,0.05)] bg-[var(--panel)] backdrop-blur-xl flex flex-col justify-between shrink-0 h-screen sticky top-0 overflow-y-auto z-10 shadow-2xl">
      <div className="p-4 lg:p-6 space-y-8">
        
        {/* Brand */}
        <div>
          <div className="font-display font-bold text-2xl tracking-tight text-[var(--bone)] flex items-center gap-2 mb-2">
            <span className="w-3 h-3 rounded-full bg-[var(--tape)] inline-block animate-signal-pulse" />
            TALENT<span className="text-[var(--tape)]">OPS</span>
          </div>
          <div className="font-mono text-[10px] lg:text-xs text-[var(--mute)] truncate">
            <span className="text-[rgba(255,255,255,0.4)] uppercase">RUN:</span>{' '}
            <span className="text-[var(--bone)]">{runTitle}</span>
          </div>
        </div>

        {/* Live Status indicator */}
        <div className="flex items-center gap-2 font-mono text-[10px] lg:text-xs">
          <span className="text-[var(--mute)]">SIGNAL:</span>
          {isLive ? (
            <span className="px-2 py-1 rounded bg-[var(--tape)]/15 text-[var(--tape)] border border-[var(--tape)]/40 flex items-center gap-1.5 w-max">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--tape)] animate-ping" />
              LIVE DEEP SEARCH
            </span>
          ) : (
            <span className="px-2 py-1 rounded bg-black/20 text-[rgba(255,255,255,0.4)] border border-[rgba(255,255,255,0.05)] w-max">
              STANDBY
            </span>
          )}
        </div>

        {/* Vertical Pipeline Rail */}
        <nav className="flex flex-col gap-0 relative">
          {SIGNAL_STAGES.map((stage, idx) => {
            const isActive = stage.id === activeStage;
            const isCompleted = completedStages.includes(stage.id) || idx < activeIndex;

            return (
              <div key={stage.id} className="relative group">
                {/* Connecting Line (Vertical) */}
                {idx > 0 && (
                  <div className="absolute left-[11px] -top-[16px] w-[2px] h-[16px] bg-[rgba(255,255,255,0.05)]">
                    <div
                      className={`w-full transition-all duration-300 ${
                        idx <= activeIndex
                          ? 'bg-[var(--tape)] shadow-[0_0_8px_rgba(204,255,0,0.6)]'
                          : 'bg-transparent'
                      }`}
                      style={{ height: idx <= activeIndex ? '100%' : '0%' }}
                    />
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => onStageSelect && onStageSelect(stage.id)}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-[var(--radius)] font-mono text-[10px] lg:text-xs transition-all duration-200 text-left ${
                    isActive
                      ? 'bg-[rgba(204,255,0,0.1)] text-[var(--tape)] font-bold shadow-inner'
                      : isCompleted
                      ? 'text-[var(--bone)] hover:bg-[rgba(255,255,255,0.05)]'
                      : 'text-[var(--mute)] opacity-60 hover:opacity-100 hover:bg-[rgba(255,255,255,0.05)]'
                  }`}
                >
                  {/* Node Dot */}
                  <span
                    className={`w-2.5 h-2.5 rounded-full shrink-0 ${
                      isActive
                        ? 'bg-[var(--tape)] animate-signal-pulse shadow-[0_0_8px_rgba(204,255,0,0.8)]'
                        : isCompleted
                        ? 'bg-[var(--tape)]/60'
                        : 'bg-slate-700'
                    }`}
                  />
                  <span className="text-sm shrink-0">{stage.icon}</span>
                  <span className="tracking-widest uppercase truncate">{stage.label}</span>
                </button>
              </div>
            );
          })}
        </nav>
      </div>

      <div className="p-4 border-t border-[rgba(255,255,255,0.05)] text-[9px] text-[rgba(255,255,255,0.3)] font-mono text-center opacity-60">
        SYS. V2 // NOHEMI EDITION
      </div>
    </aside>
  );
}
