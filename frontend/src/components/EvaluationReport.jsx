import React, { useState, useEffect } from 'react';
import { Printer, MessageSquare } from 'lucide-react';
import TranscriptBlock from './TranscriptBlock';
import ScorecardView from './ScorecardView';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function EvaluationReport({ interviewId, initialData = null }) {
  const [evaluation, setEvaluation] = useState(initialData);
  const [loading, setLoading] = useState(!initialData);
  const [error, setError] = useState('');
  // searchQuery removed

  useEffect(() => {
    let isMounted = true;
    let pollCount = 0;
    const MAX_POLLS = 15;
    let pollTimer = null;
    let fetchTimer = null;

    async function fetchEvaluation() {
      if (!interviewId) return;
      setError('');
      try {
        const res = await fetch(`${API_BASE}/api/interviews/${interviewId}/evaluation`, {
          headers: {
            'Content-Type': 'application/json',
            'X-User-Role': 'hr',
          },
        });
        if (res.status === 404) {
          pollCount++;
          if (pollCount < MAX_POLLS) {
            pollTimer = setTimeout(fetchEvaluation, 5000);
          } else {
            if (isMounted) {
              setError('Evaluation report is taking longer than expected. Please refresh.');
              setLoading(false);
            }
          }
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to fetch evaluation: ${res.statusText}`);
        }
        const data = await res.json();
        if (isMounted) {
          setEvaluation(data);
          setLoading(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Error loading candidate evaluation report');
          setLoading(false);
        }
      }
    }

    if (initialData) {
      setEvaluation(initialData);
      setLoading(false);
    } else {
      if (!evaluation) setLoading(true);
      fetchTimer = setTimeout(() => {
        fetchEvaluation();
      }, 0);
    }

    return () => {
      isMounted = false;
      if (pollTimer) clearTimeout(pollTimer);
      if (fetchTimer) clearTimeout(fetchTimer);
    };
  }, [interviewId, initialData]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) {
    return (
      <div className="panel p-8 text-center font-mono text-xs text-[var(--tape)] animate-pulse">
        ⚡ SYNTHESIZING CANDIDATE EVALUATION REPORT &amp; RAG TRANSCRIPT EVIDENCE...
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel p-6 border-[var(--alert)] bg-[var(--alert)]/10 text-[var(--alert)] flex items-center justify-between">
        <div className="font-mono text-xs">
          <strong>⚠️ EVALUATION ERROR:</strong> {error}
        </div>
        <button
          onClick={() => window.location.reload()}
          className="px-3 py-1.5 bg-[var(--panel)] border border-[var(--alert)]/50 text-xs font-mono rounded text-[var(--alert)] hover:bg-[var(--alert)]/20"
        >
          RETRY
        </button>
      </div>
    );
  }

  const rec = evaluation?.final_recommendation || {};
  const metrics = evaluation?.behavioral_metrics || {};
  const competencies = evaluation?.detailed_competencies || [];
  const turns = evaluation?.full_transcript_evaluations || [];
  const candidateId = evaluation?.candidate_id || 'Candidate';
  const needsReview = evaluation?.needs_human_review || evaluation?.scorecard?.needs_human_review || rec.needs_human_review || false;

  return (
    <div className="space-y-6 text-sm text-[var(--bone)] print:text-black print:bg-white">
      
      {/* LOUDEST ELEMENT: Persistent Alert Coral Banner when needs_human_review is true */}
      {needsReview && (
        <div className="w-full bg-[var(--alert)] text-[var(--ink)] font-mono text-sm font-bold uppercase py-3.5 px-6 rounded-[var(--radius)] flex items-center justify-between shadow-[0_0_20px_rgba(255,107,91,0.5)] border border-[#ff6b5b]">
          <div className="flex items-center gap-3">
            <span className="text-2xl animate-bounce">⚠️</span>
            <span>NEEDS HUMAN REVIEW // CANDIDATE ROUTED FOR RECRUITER AUDIT</span>
          </div>
          <span className="text-xs underline cursor-pointer bg-black/20 px-3 py-1 rounded-[var(--radius)]">ACTION REQUIRED</span>
        </div>
      )}

      {/* Header Info */}
      <div className="panel p-6 bg-[var(--panel)] space-y-4">
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="font-mono text-xs text-[var(--signal)]">
              // EVALUATION REPORT // ID: {interviewId}
            </div>
            <h2 className="font-display text-2xl font-bold text-[var(--bone)] mt-1">
              CANDIDATE: {candidateId}
            </h2>
            <p className="font-body text-xs text-[var(--mute)]">
              Evaluated at: {rec.evaluated_at ? new Date(rec.evaluated_at).toLocaleString() : 'Just now'}
            </p>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs">
            <div className="px-3 py-1.5 rounded-[var(--radius)] bg-slate-950 border border-slate-800 text-right">
              <span className="text-[var(--mute)] block text-[10px]">RECOMMENDATION</span>
              <span className="font-bold text-[var(--tape)] text-sm">{rec.hiring_recommendation || 'PENDING'}</span>
            </div>
            <button
              onClick={handlePrint}
              className="px-4 py-2 bg-[var(--panel)] border border-slate-700 hover:border-[var(--tape)] rounded-[var(--radius)] font-bold text-xs flex items-center gap-1.5"
            >
              <Printer size={14} /> EXPORT PDF
            </button>
          </div>
        </div>

        {/* Executive Summary */}
        <div className="bg-slate-950 p-4 rounded-[var(--radius)] border border-slate-800 space-y-1">
          <h3 className="font-mono text-xs font-semibold text-[var(--signal)] uppercase">
            // EXECUTIVE SUMMARY
          </h3>
          <p className="font-body text-sm text-[var(--bone)] leading-relaxed">
            {rec.executive_summary || 'No executive summary available yet.'}
          </p>
        </div>
      </div>

      {/* Extractive Scorecard Component View */}
      <ScorecardView
        interviewId={interviewId}
        scorecardData={evaluation?.scorecard || null}
      />

      {/* Interactive Transcript Log with Machine Evidence */}
      <div className="panel p-6 bg-[var(--panel)] space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="font-mono text-xs text-[var(--signal)] uppercase tracking-wider font-semibold flex items-center gap-2">
            <MessageSquare size={14} /> // INTERACTIVE TRANSCRIPT &amp; RAG EVIDENCE TRAJECTORY
          </h3>
        </div>

        <div className="space-y-3">
          {turns.length === 0 ? (
            <p className="font-mono text-xs text-[var(--mute)] italic">No turns logged yet.</p>
          ) : (
            turns.map((turn, idx) => (
              <div key={idx} className="panel p-4 bg-slate-950/80 border-slate-800 space-y-2">
                <div className="flex justify-between items-center font-mono text-xs text-[var(--mute)] border-b border-slate-900 pb-1">
                  <span>TURN #{turn.question_number || idx + 1}</span>
                  <span className="text-[var(--tape)]">ACCURACY: {turn.technical_accuracy || 85}%</span>
                </div>

                <div className="font-body text-sm font-semibold text-[var(--bone)]">
                  Q: {turn.question}
                </div>

                <TranscriptBlock
                  speaker="CANDIDATE ANSWER"
                  timestamp={`TURN-${idx + 1}`}
                  isEvidence={true}
                >
                  "{turn.candidate_answer}"
                </TranscriptBlock>
              </div>
            ))
          )}
        </div>
      </div>

    </div>
  );
}
