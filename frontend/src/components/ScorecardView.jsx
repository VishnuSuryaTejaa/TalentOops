import React, { useEffect, useState } from 'react';
import TranscriptBlock from './TranscriptBlock';

/**
 * ScorecardView Component
 * 
 * Implements Phase 6 Scorecard & Evaluation View requirements:
 * - Competency breakdown as horizontal amber (--tape) meters with exact numeric technical_accuracy value in mono.
 * - Persistent alert-coral (--alert) loud banner when needs_human_review is true.
 * - Evidence quotes as TranscriptBlock excerpts with a thin cyan (--signal) left-border.
 */
export default function ScorecardView({ supabase, interviewId, scorecardData = null }) {
  const [scorecard, setScorecard] = useState(scorecardData);
  const [loading, setLoading] = useState(!scorecardData);

  useEffect(() => {
    if (scorecardData) {
      setScorecard(scorecardData);
      setLoading(false);
      return;
    }

    if (!supabase || !interviewId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    const fetchScorecard = async () => {
      const { data, error } = await supabase
        .from('scorecards')
        .select('*')
        .eq('interview_id', interviewId)
        .order('created_at', { ascending: false })
        .limit(1)
        .single();
        
      if (!error && data) {
        setScorecard(data.scorecard);
      }
      setLoading(false);
    };

    fetchScorecard();

    const channel = supabase
      .channel(`scorecard:${interviewId}`)
      .on('postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'scorecards', filter: `interview_id=eq.${interviewId}` },
        (payload) => setScorecard(payload.new.scorecard)
      )
      .subscribe();

    return () => { supabase.removeChannel(channel); };
  }, [supabase, interviewId, scorecardData]);

  const needsReview = scorecard?.needs_human_review || false;

  return (
    <div className="panel p-6 bg-[var(--panel)] space-y-6">
      
      {/* LOUDEST ELEMENT ON THE PAGE: Persistent Alert Coral Banner when needs_human_review is true */}
      {needsReview && (
        <div className="w-full bg-[var(--alert)] text-[var(--ink)] font-mono text-sm font-bold uppercase py-3 px-6 rounded-[var(--radius)] flex items-center justify-between shadow-[0_0_20px_rgba(255,107,91,0.5)] border border-[#ff6b5b]">
          <div className="flex items-center gap-3">
            <span className="text-xl animate-bounce">⚠️</span>
            <span>NEEDS HUMAN REVIEW // ESCALATION FLAG TRIGGERED</span>
          </div>
          <span className="text-xs underline cursor-pointer bg-black/20 px-3 py-1 rounded-[var(--radius)]">ROUTE TO RECRUITER</span>
        </div>
      )}

      {/* Header Overview */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-4">
        <div>
          <h3 className="font-display text-lg font-bold text-[var(--bone)]">
            EVALUATION SCORECARD // {interviewId || 'PENDING'}
          </h3>
          <p className="font-mono text-xs text-[var(--mute)]">
            Extractive EvaluatorAgent Benchmarks &amp; Transcript Evidence
          </p>
        </div>
        <div className="font-mono text-sm text-right">
          <span className="text-[var(--mute)] text-xs block">OVERALL FIT</span>
          <span className="font-bold text-[var(--tape)] text-xl">
            {scorecard?.overall_fit ? `${(scorecard.overall_fit * 100).toFixed(0)}%` : 'PENDING'}
          </span>
        </div>
      </div>

      {/* Competencies Breakdown */}
      <div className="space-y-4">
        {loading ? (
          <div className="font-mono text-xs text-[var(--tape)] animate-pulse p-4 text-center">
            ⚡ SYNTHESIZING COMPETENCY BENCHMARKS...
          </div>
        ) : !scorecard || !scorecard.competencies || scorecard.competencies.length === 0 ? (
          <div className="font-mono text-xs text-[var(--mute)] italic p-4 text-center">
            Awaiting post-interview scorecard evaluation.
          </div>
        ) : (
          scorecard.competencies.map((comp, idx) => {
            const rawScore = comp.technical_accuracy ?? (comp.demonstrated_level === 'high' ? 90 : comp.demonstrated_level === 'medium' ? 75 : 50);
            const scoreFraction = (rawScore / 100).toFixed(2);

            return (
              <div key={idx} className="panel p-4 bg-slate-950/80 border-slate-800 space-y-3">
                
                {/* Competency Title + Numeric Value in Mono */}
                <div className="flex justify-between items-center font-mono">
                  <span className="font-semibold text-sm text-[var(--bone)] uppercase tracking-wider">
                    {comp.competency_id?.replace(/_/g, ' ')}
                  </span>
                  {/* Raw Numeric technical_accuracy in IBM Plex Mono to the right */}
                  <span className="font-bold text-sm text-[var(--tape)]">
                    ACCURACY: {scoreFraction} / 1.00 ({rawScore}%)
                  </span>
                </div>

                {/* Horizontal Amber Meter */}
                <div className="h-3 w-full bg-slate-900 rounded-[var(--radius)] overflow-hidden border border-slate-800 flex p-0.5 gap-0.5">
                  {Array.from({ length: 20 }).map((_, barIdx) => {
                    const filled = rawScore >= (barIdx + 1) * 5;
                    return (
                      <div
                        key={barIdx}
                        className={`h-full flex-1 rounded-[1px] transition-all duration-300 ${
                          filled
                            ? 'bg-[var(--tape)] shadow-[0_0_4px_var(--tape)]'
                            : 'bg-slate-900'
                        }`}
                      />
                    );
                  })}
                </div>

                {/* Machine Evidence Quotes using TranscriptBlock with cyan left-border */}
                {(comp.evidence_quotes || comp.quotes || []).length > 0 && (
                  <div className="pt-2 space-y-1">
                    <span className="font-mono text-[10px] uppercase text-[var(--signal)] font-semibold">
                      // EXTRACTED MACHINE EVIDENCE (CYAN BOUNDARY):
                    </span>
                    {(comp.evidence_quotes || comp.quotes).map((q, qIdx) => (
                      <TranscriptBlock
                        key={qIdx}
                        speaker="VERBATIM EVIDENCE"
                        timestamp="EXTRACTED TURN"
                        isEvidence={true}
                      >
                        "{typeof q === 'object' ? q.quote : q}"
                      </TranscriptBlock>
                    ))}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

    </div>
  );
}
