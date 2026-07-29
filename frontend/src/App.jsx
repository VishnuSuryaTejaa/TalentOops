import React, { useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import PipelineDashboardView from './components/PipelineDashboardView';
import HREvaluationDashboard from './components/HREvaluationDashboard';
import InterviewRoom from './components/InterviewRoom';
import ScorecardView from './components/ScorecardView';
import FairnessHeatmap from './components/FairnessHeatmap';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://qzthddhmxdcocikdhumh.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InF6dGhkZGhteGRjb2Npa2RodW1oIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQxNjc4MjAsImV4cCI6MjA5OTc0MzgyMH0.VJbR0Ad8t9SgsAPc9XyFM3bkLrPocmEekjOnnPwoJss';
const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

function App() {
  // Interview Room route: /interview/{room_id} renders full-screen control room
  const pathMatch = window.location.pathname.match(/^\/interview\/([\w-]+)/);
  if (pathMatch) {
    return <InterviewRoom roomId={pathMatch[1]} />;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const [roleId] = useState(urlParams.get('roleId') || '');
  const [candidateId] = useState(urlParams.get('candidateId') || '');
  const [interviewId, setInterviewId] = useState(urlParams.get('interviewId') || '');
  const [activeTab, setActiveTab] = useState(urlParams.get('tab') || 'dashboard'); // 'dashboard' | 'hr' | 'scorecard'

  const [goal, setGoal] = useState('');
  const [standard, setStandard] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [running, setRunning] = useState(false);
  const [activeNode, setActiveNode] = useState('sourcing');
  const [completedNodes, setCompletedNodes] = useState([]);
  const [runResult, setRunResult] = useState(null);

  const handleRunPipeline = async () => {
    setRunning(true);
    setActiveNode('sourcing');
    setCompletedNodes([]);
    setRunResult(null);

    try {
      let corpus = [];
      if (selectedFile) {
        const fileBase64 = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result.split(',')[1] || reader.result);
          reader.onerror = reject;
          reader.readAsDataURL(selectedFile);
        });

        const uploadRes = await fetch(`${API_BASE}/upload_resume`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_name: selectedFile.name, content: fileBase64 })
        });
        const uploadData = await uploadRes.json();
        if (uploadData.path) {
          corpus.push({ id: selectedFile.name.replace('.pdf', ''), pdf_path: uploadData.path });
        }
      }

      const response = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, standard, corpus })
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      setRunResult(data);

      if (data.final_state) {
        setCompletedNodes(data.final_state.completed || ['sourcing', 'screening', 'scheduling']);
        if (data.final_state.top_candidate) {
          setInterviewId(`iv-${data.final_state.top_candidate}`);
        }
      }
    } catch (err) {
      console.error('Pipeline error:', err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--ink)] text-[var(--bone)]">
      
      {/* Control Room Tab Switcher Header */}
      <div className="bg-slate-950 border-b border-slate-800 px-6 py-2 flex items-center justify-between font-mono text-xs select-none">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => setActiveTab('dashboard')}
            className={`px-3 py-1 rounded-[var(--radius)] font-bold transition-all ${
              activeTab === 'dashboard'
                ? 'bg-[var(--tape)] text-[var(--ink)] shadow-[0_0_8px_rgba(232,163,61,0.4)]'
                : 'text-[var(--mute)] hover:text-[var(--bone)]'
            }`}
          >
            🎛️ PIPELINE DASHBOARD
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('hr')}
            className={`px-3 py-1 rounded-[var(--radius)] font-bold transition-all ${
              activeTab === 'hr'
                ? 'bg-[var(--signal)] text-[var(--ink)] shadow-[0_0_8px_rgba(95,211,196,0.4)]'
                : 'text-[var(--mute)] hover:text-[var(--bone)]'
            }`}
          >
            🧠 HR DEBRIEF &amp; EVALUATION
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('scorecard')}
            className={`px-3 py-1 rounded-[var(--radius)] font-bold transition-all ${
              activeTab === 'scorecard'
                ? 'bg-slate-800 text-[var(--bone)] border border-slate-700'
                : 'text-[var(--mute)] hover:text-[var(--bone)]'
            }`}
          >
            📊 FAIRNESS &amp; SCORECARD
          </button>
        </div>

        <div className="hidden sm:flex items-center gap-2 text-[10px] text-[var(--mute)]">
          <span>SUPABASE_SYNC: {supabase ? 'CONNECTED' : 'STANDALONE'}</span>
          <span>|</span>
          <span>INTERVIEW_ID: {interviewId}</span>
        </div>
      </div>

      {/* Main Tab Render */}
      {activeTab === 'dashboard' && (
        <PipelineDashboardView
          goal={goal}
          setGoal={setGoal}
          standard={standard}
          setStandard={setStandard}
          selectedFile={selectedFile}
          setSelectedFile={setSelectedFile}
          running={running}
          handleRunPipeline={handleRunPipeline}
          activeNode={activeNode}
          completedNodes={completedNodes}
          runResult={runResult}
          onSelectCandidate={() => setActiveTab('hr')}
          onStageSelect={(stageId) => setActiveNode(stageId)}
        />
      )}

      {activeTab === 'hr' && (
        <div className="max-w-7xl mx-auto p-6">
          <HREvaluationDashboard interviewId={interviewId} />
        </div>
      )}

      {activeTab === 'scorecard' && (
        <div className="max-w-7xl mx-auto p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
          <FairnessHeatmap roleId={roleId} />
          <ScorecardView supabase={supabase} interviewId={interviewId} />
        </div>
      )}

    </div>
  );
}

export default App;
