import React, { useState } from 'react';
import { Rocket, Loader2, PhoneOff, Copy, ExternalLink } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function DeployBot({ roleId, candidateId, interviewId, onDeployed, onEnded }) {
  const [roomId,    setRoomId]    = useState('');
  const [roomUrl,   setRoomUrl]   = useState('');
  const [creating,  setCreating]  = useState(false);
  const [ending,    setEnding]    = useState(false);
  const [copied,    setCopied]    = useState(false);
  const [error,     setError]     = useState(null);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/interviews/deploy`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_id: candidateId,
          role_id:      roleId,
          interview_id: interviewId || undefined,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      setRoomId(data.room_id);
      setRoomUrl(data.room_url);
      if (data.interview_id && onDeployed) onDeployed(data.interview_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleEnd = async () => {
    setEnding(true);
    setError(null);
    try {
      await fetch(`${API_BASE}/api/rooms/${roomId}/end`, { method: 'POST' });
      setRoomId('');
      setRoomUrl('');
      if (onEnded) onEnded();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnding(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(roomUrl).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {!roomId ? (
        <button
          id="btn-create-room"
          onClick={handleCreate}
          disabled={creating}
          className="flex items-center gap-2 bg-gradient-to-r from-cyan-600 to-cyan-500
                     hover:from-cyan-500 hover:to-cyan-400 text-white px-4 py-2 rounded-md
                     font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed
                     shadow-[0_0_15px_rgba(6,182,212,0.4)]"
        >
          {creating ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
          Create Interview Room
        </button>
      ) : (
        <>
          {/* room URL chip */}
          <span className="bg-[var(--color-glass-base)] border border-[var(--color-glass-border)]
                           rounded-md px-3 py-1.5 font-mono text-xs text-cyan-300 truncate max-w-[220px]"
                title={roomUrl}>
            {roomUrl}
          </span>

          {/* copy */}
          <button
            id="btn-copy-room-url"
            onClick={handleCopy}
            className="flex items-center gap-1.5 bg-white/10 hover:bg-white/15 border border-white/15
                       text-slate-300 px-3 py-2 rounded-md text-sm transition-all"
            title="Copy room URL"
          >
            <Copy size={14} />
            {copied ? 'Copied!' : 'Copy'}
          </button>

          {/* open */}
          <a
            id="btn-open-room"
            href={roomUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 bg-cyan-600/20 border border-cyan-500/30
                       text-cyan-300 hover:bg-cyan-500/30 px-3 py-2 rounded-md text-sm transition-all"
          >
            <ExternalLink size={14} /> Open
          </a>

          {/* end */}
          <button
            id="btn-end-room"
            onClick={handleEnd}
            disabled={ending}
            className="flex items-center gap-2 bg-[var(--color-glass-base)] border border-rose-500/50
                       hover:bg-rose-500/20 text-rose-400 px-4 py-2 rounded-md font-medium
                       transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            title="End Interview Room"
          >
            {ending ? <Loader2 size={16} className="animate-spin" /> : <PhoneOff size={16} />}
            End & Evaluate
          </button>
        </>
      )}
      {error && <span className="text-rose-500 text-sm ml-2">{error}</span>}
    </div>
  );
}
