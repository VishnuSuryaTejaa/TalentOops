import React, { useState, useEffect } from 'react';
import SignatureWaveform from './SignatureWaveform';
import TranscriptBlock from './TranscriptBlock';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

/**
 * HRDebriefCard Component
 * 
 * Implements HR Debrief Room voice Q&A with Manager Agent.
 * Uses cyan (--signal) waveform and TranscriptBlock with cyan evidence border.
 */
export default function HRDebriefCard({ interviewId = '', candidateId = '' }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hrQuestion, setHrQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [qaHistory, setQaHistory] = useState([]);
  const [audioUrl, setAudioUrl] = useState('');

  useEffect(() => {
    let isMounted = true;
    async function fetchDebrief() {
      setLoading(true);
      try {
        const res = await fetch(`${API_BASE}/api/debrief/${interviewId}`, {
          headers: {
            'Content-Type': 'application/json',
            'X-User-Role': 'hr',
          },
        });
        if (res.ok) {
          const data = await res.json();
          if (isMounted) {
            setSession(data);
          }
        }
      } catch (err) {
        console.error('Error fetching HR debrief session:', err);
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    if (interviewId) {
      fetchDebrief();
    }
  }, [interviewId]);

  const handleAskManager = async (e) => {
    e.preventDefault();
    if (!hrQuestion.trim() || asking) return;

    const currentQ = hrQuestion;
    setHrQuestion('');
    setAsking(true);

    try {
      const res = await fetch(`${API_BASE}/api/debrief/turn`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          interview_id: interviewId,
          hr_question: currentQ,
        }),
      });
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }
      const data = await res.json();

      setQaHistory((prev) => [
        ...prev,
        {
          question: currentQ,
          response: data.response_text,
          audio_b64: data.audio_b64,
        },
      ]);

      if (data.audio_b64) {
        setAudioUrl(`data:audio/wav;base64,${data.audio_b64}`);
      }
    } catch (err) {
      console.error('Error asking Manager Agent:', err);
      setQaHistory((prev) => [
        ...prev,
        {
          question: currentQ,
          response: `Error: Unable to connect to Manager Agent (${err.message})`,
        },
      ]);
    } finally {
      setAsking(false);
    }
  };

  if (!interviewId) {
    return (
      <div className="panel p-4 text-center font-mono text-xs text-[var(--mute)] border-slate-800">
        NO INTERVIEW SELECTED FOR HR DEBRIEF.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="panel p-4 text-center font-mono text-xs text-[var(--signal)] animate-pulse border-[var(--signal)]/40">
        ⚡ CONNECTING TO MANAGER AGENT HR DEBRIEF CHANNEL...
      </div>
    );
  }

  const roomUrl = session?.room_url || `http://localhost:8000/interview/debrief-${interviewId.slice(0, 8)}`;
  const status = session?.status || 'MANAGER AGENT WAITING';

  return (
    <div className="panel flex flex-col bg-[var(--panel)] border-[var(--signal)]/40 overflow-hidden shadow-[0_0_15px_rgba(95,211,196,0.1)]">
      
      {/* Control Room Broadcast Bar - HR Debrief Chrome */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-[#0F131D]/90 select-none">
        <div className="flex items-center gap-3">
          <span className="font-display font-extrabold text-base tracking-tight text-[var(--bone)]">
            TALENT<span className="text-[var(--signal)]">OPS</span> <span className="text-slate-700 font-mono text-xs font-normal ml-1">| HR DEBRIEF</span>
          </span>
          <span className="text-slate-700 font-mono text-xs ml-1">|</span>
          <span className="font-mono text-xs text-[var(--mute)]">
            CANDIDATE ID: <span className="text-[var(--bone)]">{session?.candidate_id || candidateId}</span>
          </span>
        </div>

        {/* Center ON AIR State Indicator */}
        <div className="font-display text-sm font-bold text-[var(--bone)] tracking-wider px-3 py-1 bg-slate-900 border border-[var(--signal)]/40 rounded-[var(--radius)] flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[var(--signal)] animate-signal-pulse" />
          {status}
        </div>

        <div className="flex items-center gap-4 font-mono text-xs">
          <a
            href={roomUrl}
            target="_blank"
            rel="noreferrer"
            className="px-3 py-1 bg-[var(--signal)]/20 text-[var(--signal)] border border-[var(--signal)]/50 hover:bg-[var(--signal)]/30 font-semibold rounded-[var(--radius)] transition-all flex items-center gap-1.5 shadow-[0_0_8px_rgba(95,211,196,0.2)]"
          >
            <span>🎙️</span> JOIN LIVE ROOM
          </a>
        </div>
      </header>

      <div className="p-6 space-y-4">
        {/* Signature Element Waveform - Cyan for HR Debrief Room */}
        <SignatureWaveform
          active={asking || Boolean(audioUrl)}
          variant="signal"
          caption="MANAGER AGENT // HR DEBRIEF VOICE CHANNEL"
        />

        {/* Interactive Manager Agent HR Q&A Form */}
        <div className="space-y-3 pt-2">
          <h4 className="font-mono text-xs font-semibold text-[var(--signal)] uppercase tracking-wider">
            // ORAL HR QUESTION INPUT (TRANSCRIPT RAG)
          </h4>

          <form onSubmit={handleAskManager} className="flex gap-2">
            <input
              type="text"
              value={hrQuestion}
              onChange={(e) => setHrQuestion(e.target.value)}
              placeholder="Ask Manager Agent (e.g. 'Why did they get a high score on database architecture?')..."
              className="flex-1 bg-slate-950 border border-slate-800 rounded-[var(--radius)] px-4 py-3 font-mono text-xs text-[var(--bone)] focus:outline-none focus:border-[var(--signal)]"
            />
            <button
              type="submit"
              disabled={asking || !hrQuestion.trim()}
              className="px-5 py-3 bg-[var(--signal)] text-[var(--ink)] font-mono font-bold text-xs rounded-[var(--radius)] hover:bg-[#72dfd1] transition-all disabled:opacity-40 shadow-[0_0_12px_rgba(95,211,196,0.3)]"
            >
              {asking ? '⚡ QUERYING...' : 'TRANSMIT QUESTION'}
            </button>
          </form>

          {/* Audio Player */}
          {audioUrl && (
            <div className="p-3 rounded-[var(--radius)] bg-slate-950 border border-[var(--signal)]/40 flex items-center justify-between gap-3 font-mono text-xs mt-2">
              <span className="text-[var(--signal)] font-semibold flex items-center gap-2">
                <span>🔊</span> MANAGER AGENT AUDIO RESPONSE:
              </span>
              <audio controls autoPlay src={audioUrl} className="h-8 w-64" />
            </div>
          )}

          {/* Q&A History Log with TranscriptBlock */}
          {qaHistory.length > 0 && (
            <div className="space-y-2 mt-4 max-h-60 overflow-y-auto pr-2">
              {qaHistory.map((item, idx) => (
                <div key={idx} className="space-y-2">
                  <div className="font-mono text-xs text-[var(--mute)] bg-slate-900/50 p-2 rounded-[var(--radius)] border border-slate-800">
                    HR QUERY: <span className="text-[var(--bone)]">{item.question}</span>
                  </div>
                  <TranscriptBlock
                    speaker="ManagerAgent"
                    timestamp={new Date().toLocaleTimeString()}
                    isEvidence={true}
                  >
                    {item.response}
                  </TranscriptBlock>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
