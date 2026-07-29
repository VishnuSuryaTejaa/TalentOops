import React, { useState, useEffect } from 'react';
import HRDebriefCard from './HRDebriefCard';
import EvaluationReport from './EvaluationReport';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function HREvaluationDashboard({ interviewId = '' }) {
  const [evaluation, setEvaluation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isPending, setIsPending] = useState(false);

  useEffect(() => {
    let isMounted = true;
    let attempts = 0;
    const MAX_ATTEMPTS = 15;

    async function fetchEvaluation() {
      if (attempts >= MAX_ATTEMPTS) {
        if (isMounted) {
          setError('Evaluation is taking too long to generate. Please try again later.');
          setLoading(false);
          setIsPending(false);
        }
        return;
      }

      attempts++;
      try {
        const res = await fetch(`${API_BASE}/api/interviews/${interviewId}/evaluation`, {
          headers: {
            'Content-Type': 'application/json',
            'X-User-Role': 'hr',
          },
        });

        if (res.status === 404) {
          if (isMounted) {
            setIsPending(true);
            setLoading(false);
            setTimeout(fetchEvaluation, 5000);
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
          setIsPending(false);
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Error loading evaluation report');
          setLoading(false);
          setIsPending(false);
        }
      }
    }

    if (interviewId) {
      setLoading(true);
      fetchEvaluation();
    }
    return () => { isMounted = false; };
  }, [interviewId]);

  if (!interviewId) {
    return (
      <div className="panel p-10 text-center text-[var(--mute)] font-mono text-xs bg-[var(--panel)]">
        NO CANDIDATE INTERVIEW SELECTED.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="panel p-10 text-center text-[var(--signal)] font-mono text-xs animate-pulse bg-[var(--panel)]">
        ⚡ LOADING HR CANDIDATE EVALUATION REPORT...
      </div>
    );
  }

  if (isPending) {
    return (
      <div className="panel p-10 text-center text-[var(--tape)] font-mono text-xs animate-pulse bg-[var(--panel)]">
        ⏳ EVALUATION IS STILL BEING PROCESSED... RETRYING AUTOMATICALLY.
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel p-6 border-[var(--alert)] bg-[var(--alert)]/10 text-[var(--alert)]">
        <h3 className="font-display font-bold mb-2">⚠️ ERROR LOADING HR EVALUATION</h3>
        <p className="text-xs font-mono">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Realtime HR Debrief Notification Card */}
      <HRDebriefCard interviewId={interviewId} candidateId={evaluation?.candidate_id || 'c-candidate'} />

      {/* Polish Candidate Evaluation Report Component */}
      <EvaluationReport interviewId={interviewId} initialData={evaluation} />
    </div>
  );
}
