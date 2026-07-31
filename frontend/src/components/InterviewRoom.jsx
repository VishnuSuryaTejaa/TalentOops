import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, MicOff, Video, VideoOff, PhoneOff, CheckCircle, XCircle, Loader2, MessageSquare } from 'lucide-react';
import SignatureWaveform from './SignatureWaveform';
import TranscriptBlock from './TranscriptBlock';

/* ─── helpers ─────────────────────────────────────────────────────────────── */
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const WS_BASE  = API_BASE.replace(/^http/, 'ws');

/* ─── stages ──────────────────────────────────────────────────────────────── */
const STAGE = {
  LOBBY:      'lobby',
  CONSENT:    'consent',
  INTERVIEW:  'interview',
  EVALUATING: 'evaluating',
  COMPLETE:   'complete',
  ERROR:      'error',
};

export default function InterviewRoom({ roomId }) {
  const [stage,       setStage]       = useState(STAGE.LOBBY);
  const [micOn,       setMicOn]       = useState(true);
  const [camOn,       setCamOn]       = useState(true);
  const [consentText, setConsentText] = useState('');
  const [disclosure,  setDisclosure]  = useState('');
  const [transcript,  setTranscript]  = useState([]);
  const [turnInput,   setTurnInput]   = useState('');
  const [fsmState,    setFsmState]    = useState('OPENING');
  const [errorMsg,    setErrorMsg]    = useState('');
  const [consentGranted, setConsentGranted] = useState(false);
  const [candidateName, setCandidateName] = useState('');

  const [totalSeconds,     setTotalSeconds]     = useState(0);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  // Remove roomMeta to avoid unused state

  const wsRef          = useRef(null);
  const localVideoRef  = useRef(null);
  const localStream    = useRef(null);
  const transcriptEnd  = useRef(null);
  const mediaRecorderRef = useRef(null);
  const micOnRef       = useRef(true);
  const stageRef       = useRef(STAGE.LOBBY);
  const countdownRef   = useRef(null);
  const selectedVoiceRef = useRef(null);

  /* ── webcam preview ─────────────────────────────────────────────────────── */
  useEffect(() => {
    let stream;
    navigator.mediaDevices?.getUserMedia({ video: true, audio: true })
      .then(s => {
        stream = s;
        localStream.current = s;
        if (localVideoRef.current) localVideoRef.current.srcObject = s;
      })
      .catch(() => {});
    return () => {
      stream?.getTracks().forEach(t => t.stop());
    };
  }, []);

  useEffect(() => {
    if (localStream.current) {
      localStream.current.getAudioTracks().forEach(t => (t.enabled = micOn));
    }
  }, [micOn]);

  useEffect(() => {
    if (localStream.current) {
      localStream.current.getVideoTracks().forEach(t => (t.enabled = camOn));
    }
  }, [camOn]);

  useEffect(() => {
    if (micOn && localStream.current && wsRef.current?.readyState === WebSocket.OPEN && stage === STAGE.INTERVIEW) {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state === 'inactive') {
        try {
          const audioStream = new MediaStream(localStream.current.getAudioTracks());
          const recorder = new MediaRecorder(audioStream, { mimeType: 'audio/webm' });
          recorder.ondataavailable = (e) => {
            if (e.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(e.data);
            }
          };
          recorder.start(500); // Send audio in 500ms chunks
          mediaRecorderRef.current = recorder;
        } catch (err) {
          console.warn('MediaRecorder start failed:', err);
        }
      }
    } else {
      if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
        try {
          mediaRecorderRef.current.stop();
        } catch {}
      }
    }
  }, [micOn, stage]);

  useEffect(() => {
    transcriptEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const pickBestVoice = useCallback(() => {
    if (selectedVoiceRef.current) return selectedVoiceRef.current;

    const voices = window.speechSynthesis?.getVoices() || [];
    if (voices.length === 0) return null;

    const preferred = ['Google UK English Female', 'Google US English', 'Samantha', 'Alex', 'Karen'];
    for (const name of preferred) {
      const v = voices.find(v => v.name === name);
      if (v) {
        selectedVoiceRef.current = v;
        return v;
      }
    }
    const defaultVoice = voices.find(v => v.lang?.startsWith('en')) || voices[0] || null;
    if (defaultVoice) {
      selectedVoiceRef.current = defaultVoice;
    }
    return defaultVoice;
  }, []);

  const speakText = useCallback((text) => {
    if (!text || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      const voice = pickBestVoice();
      if (voice) utterance.voice = voice;
      utterance.rate = 0.95;
      utterance.pitch = 1.05;
      utterance.volume = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('Speech synthesis failed:', e);
    }
  }, [pickBestVoice]);

  useEffect(() => {
    micOnRef.current = micOn;
  }, [micOn]);

  useEffect(() => {
    stageRef.current = stage;
    if (stage === STAGE.COMPLETE) {
      window.location.href = `/?interviewId=${roomId}&tab=hr`;
    }
  }, [stage, roomId]);

  /* ── WebSocket connection ───────────────────────────────────────────────── */
  const connectWs = useCallback(() => {
    if (!roomId) return;
    const ws = new WebSocket(`${WS_BASE}/api/ws/room/${roomId}`);
    wsRef.current = ws;

    ws.onopen = () => setStage(STAGE.CONSENT);

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      const { type, data } = msg;

      switch (type) {
        case 'room-joined':
          if (data.candidate_name) {
            setCandidateName(data.candidate_name);
          }
          break;

        case 'consent-ask':
          const askText = data.text || '';
          setDisclosure(askText);
          speakText(askText);
          break;

        case 'agent-message': {
          const agentText = data.text || '';
          if (data.fsm_state) {
            setFsmState(data.fsm_state.toUpperCase());
          }
          if (data.agent === 'consent') {
            if (data.consent_granted) {
              setConsentGranted(true);
              setStage(STAGE.INTERVIEW);
            } else {
              setStage(STAGE.ERROR);
              setErrorMsg('Consent was not granted. Session ended.');
            }
          } else if (data.event === 'interview_duration' && data.duration_seconds > 0) {
            setTotalSeconds(data.duration_seconds);
            setRemainingSeconds(data.duration_seconds);
            if (countdownRef.current) clearInterval(countdownRef.current);
            countdownRef.current = setInterval(() => {
              setRemainingSeconds(prev => {
                if (prev <= 1) { clearInterval(countdownRef.current); return 0; }
                return prev - 1;
              });
            }, 1000);
          } else if (agentText) {
            setTranscript(prev => prev.some(t => t.text === agentText) ? prev : [
              ...prev, { speaker: 'interviewer', text: agentText },
            ]);
            speakText(agentText);
          }
          break;
        }

        case 'interview-turn':
          if (data.text) {
            const text = data.text;
            const speaker = data.speaker || 'interviewer';
            if (data.fsm_state) setFsmState(data.fsm_state.toUpperCase());
            setTranscript(prev => {
              if (prev.length > 0 && prev[prev.length - 1].speaker === speaker && prev[prev.length - 1].text === text) {
                return prev;
              }
              return [...prev, { speaker, text }];
            });
            if (speaker === 'interviewer' || speaker === 'agent') {
              speakText(text);
            }
          }
          break;

        case 'eval-update':
        case 'session-end': {
          if (type === 'session-end' || data.status === 'completed') {
            setStage(STAGE.COMPLETE);
          } else {
            setStage(STAGE.EVALUATING);
          }
          break;
        }

        case 'error':
          setStage(STAGE.ERROR);
          setErrorMsg(data.message || 'An unknown error occurred.');
          break;

        default:
          break;
      }
    };

    ws.onerror = () => {
      setStage(STAGE.ERROR);
      setErrorMsg('WebSocket connection lost. Please refresh and try again.');
    };

    ws.onclose = () => { wsRef.current = null; };
  }, [roomId, speakText]);

  useEffect(() => {
    if (roomId) {
      connectWs();
    }
  }, [roomId, connectWs]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.onmessage = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  const sendFrame = (type, data = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, data }));
    }
  };

  const handleJoin = () => connectWs();

  const handleConsent = (textInput = consentText) => {
    const text = textInput || 'Yes, I consent to the interview recording.';
    setConsentGranted(true);
    setTranscript([{ speaker: 'interviewer', text: disclosure }]);
    sendFrame('consent-response', { text });
  };

  const handleDecline = () => {
    setConsentGranted(false);
    sendFrame('session-end');
    setStage(STAGE.ERROR);
    setErrorMsg('Consent declined. Session ended.');
  };

  const handleTurnSend = useCallback((overrideText) => {
    const textToSend = typeof overrideText === 'string' ? overrideText : turnInput;
    // Do not check for empty text because we might be sending binary audio instead
    
    // We do not eagerly append to transcript locally, we wait for backend broadcast
    const finalizeTurn = () => {
      sendFrame('interview-turn', { text: textToSend.trim() });
      setTurnInput('');
      setMicOn(false);
    };

    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.onstop = finalizeTurn;
      mediaRecorderRef.current.stop();
    } else {
      finalizeTurn();
    }
  }, [turnInput]);

  const handleEnd = async () => {
    sendFrame('session-end');
    wsRef.current?.close();
    await fetch(`${API_BASE}/api/rooms/${roomId}/end`, { method: 'POST' }).catch(() => {});
    setStage(STAGE.COMPLETE);
  };

  return (
    <div className="min-h-screen bg-[var(--ink)] text-[var(--bone)] font-body flex flex-col">

      {/* Control Room Broadcast Bar */}
      <header className="flex items-center justify-between px-6 py-3 border-b border-slate-800 bg-[#0F131D]/90 backdrop-blur select-none">
        <div className="flex items-center gap-3">
          <span className="font-display font-extrabold text-base tracking-tight text-[var(--bone)]">
            TALENT<span className="text-[var(--tape)]">OPS</span>
          </span>
          <span className="text-slate-700 font-mono text-xs">|</span>
          {/* Candidate Identity Reduced to Mono Label (Fairness Model Constraint) */}
          <span className="font-mono text-xs text-[var(--mute)]">
            CANDIDATE: <span className="text-[var(--bone)]">{candidateName || 'Unknown'}</span>
          </span>
        </div>

        {/* Center ON AIR State Indicator (Bricolage Grotesque) */}
        {stage === STAGE.INTERVIEW && (
          <div className="font-display text-base font-bold text-[var(--bone)] tracking-wider px-3 py-1 bg-[var(--panel)] border border-slate-800 rounded-[var(--radius)] flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[var(--tape)] animate-signal-pulse" />
            ON AIR // {fsmState}
          </div>
        )}

        <div className="flex items-center gap-4 font-mono text-xs">
          {totalSeconds > 0 && (
            <div className="px-3 py-1 rounded-[var(--radius)] bg-slate-900 border border-slate-800 text-[var(--mute)]">
              RECORDING: {Math.floor(remainingSeconds / 60)}:{(remainingSeconds % 60).toString().padStart(2, '0')}
            </div>
          )}
          <button
            type="button"
            onClick={handleEnd}
            className="px-3 py-1 rounded-[var(--radius)] bg-[var(--alert)]/20 text-[var(--alert)] border border-[var(--alert)]/50 hover:bg-[var(--alert)]/30 font-semibold"
          >
            END ROOM
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        
        {/* Left Video Stream Sidebar */}
        <div className="w-64 flex-shrink-0 flex flex-col gap-4 p-4 border-r border-slate-800 bg-[var(--panel)]/50">
          <div className="relative rounded-[var(--radius)] overflow-hidden bg-slate-950 aspect-video border border-slate-800">
            <video
              ref={localVideoRef}
              autoPlay
              muted
              playsInline
              className={`w-full h-full object-cover ${!camOn ? 'opacity-0' : ''}`}
            />
            {!camOn && (
              <div className="absolute inset-0 flex items-center justify-center">
                <VideoOff size={24} className="text-slate-600" />
              </div>
            )}
            <div className="absolute bottom-2 left-2 text-[10px] font-mono bg-black/70 px-2 py-0.5 rounded text-[var(--mute)]">
              FEED // LOCAL_CAM
            </div>
          </div>

          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setMicOn(v => !v)}
              className={`flex-1 py-1.5 rounded-[var(--radius)] font-mono text-xs border transition-all ${
                micOn
                  ? 'bg-slate-900 border-slate-700 text-[var(--bone)]'
                  : 'bg-[var(--alert)]/20 border-[var(--alert)] text-[var(--alert)]'
              }`}
            >
              {micOn ? 'MIC: ON' : 'MIC: OFF'}
            </button>
            <button
              type="button"
              onClick={() => setCamOn(v => !v)}
              className={`flex-1 py-1.5 rounded-[var(--radius)] font-mono text-xs border transition-all ${
                camOn
                  ? 'bg-slate-900 border-slate-700 text-[var(--bone)]'
                  : 'bg-[var(--alert)]/20 border-[var(--alert)] text-[var(--alert)]'
              }`}
            >
              {camOn ? 'CAM: ON' : 'CAM: OFF'}
            </button>
          </div>
        </div>

        {/* Center Main Stage Room */}
        <div className="flex-1 flex flex-col items-center justify-center p-6 overflow-y-auto">

          {/* LOBBY STAGE */}
          {stage === STAGE.LOBBY && (
            <div className="w-full max-w-md panel p-6 space-y-6 text-center">
              <div className="space-y-2">
                <h1 className="font-display text-2xl font-bold text-[var(--bone)]">
                  ENTERING INTERVIEW ROOM
                </h1>
                <p className="font-mono text-xs text-[var(--mute)]">
                  Verify audio capture permissions before connecting to the Oral Interview Agent.
                </p>
              </div>
              <button
                type="button"
                id="btn-join-room"
                onClick={handleJoin}
                className="w-full py-3 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-sm font-bold hover:bg-[#e6ff00] shadow-[0_0_15px_rgba(204,255,0,0.3)] transition-all"
              >
                CONNECT SIGNAL CHANNEL
              </button>
            </div>
          )}

          {/* CONSENT STAGE - Matching Section 2.3 of Design Pitch */}
          {stage === STAGE.CONSENT && (
            <div className="w-full max-w-lg panel p-8 space-y-6">
              
              {/* Stilled Amber Waveform Bar (Unlit -> Lit on Consent) */}
              <SignatureWaveform
                active={consentGranted}
                variant="tape"
                barCount={1}
                caption={consentGranted ? 'RECORDING — LIVE' : 'RECORDING — NOT STARTED'}
              />

              <div className="space-y-2 text-center">
                <h2 className="font-display text-xl font-bold text-[var(--bone)]">
                  RECORDING DISCLOSURE &amp; CONSENT
                </h2>
                <p className="font-body text-xs text-[var(--mute)] leading-relaxed">
                  Please review the consent protocol below. TalentOps uses structured STT audio processing to evaluate competencies against objective hiring standards.
                </p>
              </div>

              <div className="panel p-4 bg-slate-950 font-body text-sm text-[var(--bone)] leading-relaxed border-slate-800">
                {disclosure || 'This oral interview session will be recorded and transcribed by OralInterviewAgent for objective standard evaluation. Do you consent to audio recording and transcription?'}
              </div>

              <input
                id="input-consent"
                type="text"
                value={consentText}
                onChange={e => setConsentText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleConsent()}
                placeholder='Type "yes I consent" to proceed…'
                className="w-full bg-slate-950 border border-slate-800 rounded-[var(--radius)] px-4 py-2.5 font-mono text-xs text-[var(--bone)] focus:outline-none focus:border-[var(--tape)]"
              />

              {/* Equal-Weight Consent Buttons (Same Size, Same Priority) */}
              <div className="flex gap-4">
                <button
                  type="button"
                  id="btn-consent-agree"
                  onClick={() => handleConsent()}
                  className="flex-1 py-3 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-xs font-bold hover:bg-[#e6ff00] transition-all"
                >
                  I CONSENT &amp; JOIN
                </button>
                <button
                  type="button"
                  id="btn-consent-decline"
                  onClick={handleDecline}
                  className="flex-1 py-3 rounded-[var(--radius)] bg-[var(--panel)] text-[var(--bone)] border border-slate-700 font-mono text-xs hover:border-[var(--alert)] hover:text-[var(--alert)] transition-all"
                >
                  DECLINE
                </button>
              </div>

            </div>
          )}

          {/* LIVE INTERVIEW STAGE - Section 2.2 */}
          {stage === STAGE.INTERVIEW && (
            <div className="w-full max-w-3xl flex flex-col h-full space-y-4">
              
              {/* Center Broadcast FSM State Indicator */}
              <div className="text-center py-2 border-b border-slate-800/80">
                <span className="font-mono text-xs text-[var(--mute)] uppercase tracking-widest">STATE MACHINE: </span>
                <span className="font-display font-bold text-lg text-[var(--tape)] tracking-wider">
                  {fsmState}
                </span>
              </div>

              {/* Transcript Scroll Area with TranscriptBlock */}
              <div className="flex-1 overflow-y-auto space-y-2 pr-2">
                {transcript.map((turn, i) => (
                  <TranscriptBlock
                    key={i}
                    speaker={turn.speaker === 'candidate' ? 'CANDIDATE' : 'OralInterviewAgent'}
                    timestamp={new Date().toLocaleTimeString()}
                    isEvidence={false}
                  >
                    {turn.text}
                  </TranscriptBlock>
                ))}
                <div ref={transcriptEnd} />
              </div>

              {/* Signature Element: Bottom Amber Waveform */}
              <SignatureWaveform
                active={true}
                variant="tape"
                caption="ORAL INTERVIEW AGENT // LIVE STT CAPTURE"
              />

              {/* Answer Input Controls */}
              <div className="flex gap-3 pt-2">
                <input
                  id="input-answer"
                  type="text"
                  value={turnInput}
                  onChange={e => setTurnInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleTurnSend()}
                  placeholder="Speak into microphone or type answer..."
                  className="flex-1 bg-slate-950 border border-slate-800 rounded-[var(--radius)] px-4 py-3 font-mono text-xs text-[var(--bone)] focus:outline-none focus:border-[var(--tape)]"
                />
                <button
                  type="button"
                  id="btn-send-turn"
                  onClick={() => handleTurnSend()}
                  disabled={!turnInput.trim() && !micOn}
                  className="px-5 py-3 rounded-[var(--radius)] bg-[var(--tape)] text-[var(--ink)] font-mono text-xs font-bold hover:bg-[#e6ff00] disabled:opacity-40 transition-all"
                >
                  TRANSMIT TURN
                </button>
              </div>

            </div>
          )}

          {/* EVALUATING STAGE */}
          {stage === STAGE.EVALUATING && (
            <div className="text-center max-w-md panel p-8 space-y-4">
              <Loader2 size={36} className="text-[var(--tape)] animate-spin mx-auto" />
              <h2 className="font-display text-xl font-bold text-[var(--bone)]">
                SYNTHESIZING CANDIDATE SCORECARD...
              </h2>
              <p className="font-mono text-xs text-[var(--mute)]">
                EvaluatorAgent is extracting technical accuracy benchmarks and transcript evidence.
              </p>
            </div>
          )}

          {/* ERROR STAGE */}
          {stage === STAGE.ERROR && (
            <div className="text-center max-w-md panel p-8 space-y-4 border-[var(--alert)]">
              <XCircle size={40} className="text-[var(--alert)] mx-auto" />
              <h2 className="font-display text-xl font-bold text-[var(--bone)]">SESSION TERMINATED</h2>
              <p className="font-mono text-xs text-[var(--mute)]">{errorMsg}</p>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
