import React, { useState } from 'react';
import SignalChainRail from './SignalChainRail';
import TapeLabelHeader from './TapeLabelHeader';
import CandidateChannelStrip from './CandidateChannelStrip';
import UploadZone from './UploadZone';

/**
 * PipelineDashboardView Component
 * 
 * Implements Phase 3: Pipeline Dashboard (Run Overview)
 * - Pinned Signal chain rail at top.
 * - Tape Label run metadata header.
 * - Candidate list rendered as a mixing console channel strip with live meters.
 */
export default function PipelineDashboardView({
  goal,
  setGoal,
  standard,
  setStandard,
  selectedFile,
  setSelectedFile,
  running,
  handleRunPipeline,
  activeNode,
  completedNodes,
  candidates = [],
  runResult,
  onSelectCandidate,
  onStageSelect
}) {
  const [activeStage, setActiveStage] = useState(activeNode || 'sourcing');

  // If runResult provides candidate room URL, reflect it on the active candidate
  const candidateList = candidates.map(c => {
    if (runResult && (c.id === 'c1' || c.name.toLowerCase().includes('alex'))) {
      const roomUrl = runResult?.final_state?.results?.scheduling?.room_url || runResult?.room_url;
      if (roomUrl) return { ...c, roomUrl, stage: 'INTERVIEW' };
    }
    return c;
  });

  return (
    <div className="min-h-screen bg-[var(--ink)] text-[var(--bone)]">
      {/* Pinned Signal Chain Rail */}
      <SignalChainRail
        activeStage={activeStage}
        completedStages={completedNodes}
        onStageSelect={(stageId) => {
          setActiveStage(stageId);
          if (onStageSelect) onStageSelect(stageId);
        }}
        runTitle={goal || 'Hire Senior Engineer'}
        isLive={running}
      />

      <main className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
        
        {/* Top Control Room Header Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          
          {/* Tape Label Header */}
          <div className="lg:col-span-2 space-y-3">
            <TapeLabelHeader
              goal={goal}
              standard={standard}
              runId={runResult?.run_id || 'run-local-01'}
            />

            {/* Run Execution Bar */}
            <div className="panel p-4 bg-[var(--panel)] flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h3 className="font-display text-base font-bold text-[var(--bone)]">
                  AUTOMATED AGENT PIPELINE
                </h3>
                <p className="font-mono text-xs text-[var(--mute)]">
                  Graph Execution: Sourcing → Screening → Scheduling → Interview → Eval → Debrief
                </p>
              </div>
              <button
                type="button"
                onClick={handleRunPipeline}
                disabled={running}
                className="px-5 py-2.5 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-xs font-bold hover:bg-[#f3b04c] transition-all shadow-[0_0_12px_rgba(232,163,61,0.3)] disabled:opacity-50 shrink-0"
              >
                {running ? '⚡ PIPELINE RUNNING...' : '▶ EXECUTE PIPELINE'}
              </button>
            </div>
          </div>

          {/* Goal Settings Form */}
          <div className="panel p-4 space-y-3 bg-[var(--panel)]">
            <h4 className="font-mono text-xs text-[var(--tape)] uppercase tracking-wider font-semibold">
              // PIPELINE PARAMETERS
            </h4>
            <div className="space-y-2">
              <div>
                <label className="text-[10px] font-mono text-[var(--mute)] uppercase">ROLE GOAL</label>
                <input
                  type="text"
                  value={goal}
                  onChange={(e) => setGoal(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-[var(--radius)] p-2 font-mono text-xs text-[var(--bone)] focus:outline-none focus:border-[var(--tape)]"
                />
              </div>
              <div>
                <label className="text-[10px] font-mono text-[var(--mute)] uppercase">STANDARD</label>
                <textarea
                  value={standard}
                  onChange={(e) => setStandard(e.target.value)}
                  rows="2"
                  className="w-full bg-slate-950 border border-slate-800 rounded-[var(--radius)] p-2 font-mono text-xs text-[var(--bone)] focus:outline-none focus:border-[var(--tape)]"
                />
              </div>
              <UploadZone onFileSelect={(file) => setSelectedFile(file)} />
            </div>
          </div>

        </div>

        {/* Mixing Console Candidate Channel Strips */}
        <section className="space-y-3 pt-2">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <h2 className="font-mono text-xs text-[var(--mute)] uppercase tracking-widest flex items-center gap-2">
              <span>🎛️</span> MIXING CONSOLE // CANDIDATE CHANNELS ({candidateList.length})
            </h2>
            <div className="font-mono text-[10px] text-[var(--mute)]">
              METER THRESHOLD: <span className="text-[var(--tape)]">0.70</span> | ALERT: <span className="text-[var(--alert)]">&lt; 0.70</span>
            </div>
          </div>

          <div className="space-y-2">
            {candidateList.map((candidate, idx) => (
              <CandidateChannelStrip
                key={candidate.id}
                channelNumber={idx + 1}
                candidate={candidate}
                onSelect={(id) => onSelectCandidate && onSelectCandidate(id)}
              />
            ))}
          </div>
        </section>

      </main>
    </div>
  );
}
