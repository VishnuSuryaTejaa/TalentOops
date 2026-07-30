import React, { useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import PipelineDashboardView from './components/PipelineDashboardView';
import HREvaluationDashboard from './components/HREvaluationDashboard';
import InterviewRoom from './components/InterviewRoom';
import ScorecardView from './components/ScorecardView';
import FairnessHeatmap from './components/FairnessHeatmap';
import SidebarNavigation from './components/SidebarNavigation';
import LiquidGradientBackground from './components/LiquidGradientBackground';

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
  
  // Stages: 'sourcing' | 'screening' | 'scheduling' | 'interview' | 'eval' | 'scorecard'
  const [activeStage, setActiveStage] = useState(urlParams.get('stage') || 'sourcing'); 
  const [candidates, setCandidates] = useState([]);

  const [goal, setGoal] = useState('');
  const [standard, setStandard] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [running, setRunning] = useState(false);
  const [completedNodes, setCompletedNodes] = useState([]);
  const [runResult, setRunResult] = useState(null);
  const [validationError, setValidationError] = useState('');

  const handleRunPipeline = async () => {
    if (!goal || !standard || !selectedFile) {
      setValidationError('Missing required details: resume, role, and standard must be provided before proceeding.');
      return;
    }

    setRunning(true);
    setActiveStage('sourcing');
    setCompletedNodes([]);
    setRunResult(null);
    setCandidates([]);
    setValidationError('');

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
        
        if (!uploadRes.ok) {
          const errMessage = uploadData.detail || `Upload failed with status ${uploadRes.status}`;
          setValidationError(errMessage);
          throw new Error(errMessage);
        }

        if (uploadData.path) {
          corpus.push({ id: uploadData.candidate_id || uploadData.path, pdf_path: uploadData.path });
        }
      }

      const response = await fetch(`${API_BASE}/run/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ goal, standard, corpus })
      });

      if (!response.ok) {
        let errMessage = `HTTP error! status: ${response.status}`;
        try {
          const errData = await response.json();
          if (errData.detail) errMessage = errData.detail;
        } catch (e) {}
        setValidationError(errMessage);
        throw new Error(errMessage);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let done = false;
      const newCompleted = ['sourcing'];
      
      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n').filter(line => line.trim() !== '');
          for (const line of lines) {
            try {
              const data = JSON.parse(line);
              if (data.type === 'update') {
                if (data.candidates) setCandidates(data.candidates);
                if (data.top_candidate) setInterviewId(`iv-${data.top_candidate}`);
                let frontendStage = (data.stage || 'unknown').toLowerCase();
                if (frontendStage === 'intake') frontendStage = 'sourcing';
                if (frontendStage === 'coordination') frontendStage = 'scheduling';
                if (frontendStage === 'waiting_for_assessment') frontendStage = 'interview';
                if (frontendStage === 'assessment') frontendStage = 'interview';
                if (frontendStage === 'evaluation') frontendStage = 'eval';
                
                if (frontendStage && frontendStage !== 'unknown') {
                   setActiveStage(frontendStage);
                   if (!newCompleted.includes(frontendStage)) {
                       newCompleted.push(frontendStage);
                       setCompletedNodes([...newCompleted]);
                   }
                }
              } else if (data.type === 'complete') {
                setRunResult(data);
                if (data.final_state) {
                  if (data.final_state.candidates) setCandidates(data.final_state.candidates);
                  setCompletedNodes(data.final_state.completed || ['sourcing', 'screening', 'scheduling']);
                  if (data.final_state.top_candidate) {
                    setInterviewId(`iv-${data.final_state.top_candidate}`);
                  }
                  setActiveStage('eval');
                }
              } else if (data.type === 'error') {
                setValidationError(data.error);
              }
            } catch (e) {
              console.error("Error parsing NDJSON line:", e, line);
            }
          }
        }
      }
    } catch (err) {
      console.error('Pipeline error:', err);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="flex min-h-screen text-[var(--bone)]">
      <LiquidGradientBackground />
      
      {/* Sidebar Navigation */}
      <SidebarNavigation
        activeStage={activeStage}
        completedStages={completedNodes}
        onStageSelect={setActiveStage}
        runTitle={goal || 'Hire Senior Engineer'}
        isLive={running}
      />

      {/* Main Content Area */}
      <main className="flex-1 min-h-screen overflow-x-hidden relative flex flex-col">
        
        {/* Top Header Information (Replaced old tab switcher) */}
        <div className="bg-[rgba(11,14,20,0.4)] backdrop-blur-md border-b border-[rgba(255,255,255,0.05)] px-6 py-3 flex flex-wrap items-center justify-between gap-4 font-mono text-xs select-none sticky top-0 z-40">
          <div className="font-display font-semibold text-[var(--bone)] tracking-wide">
            CURRENT STAGE: <span className="text-[var(--tape)] ml-2">{activeStage.toUpperCase()}</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-[var(--mute)]">
            <div className="flex items-center gap-1.5">
              <span className={`w-1.5 h-1.5 rounded-full ${supabase ? 'bg-[var(--signal)]' : 'bg-slate-600'}`}></span>
              SUPABASE: {supabase ? 'CONNECTED' : 'STANDALONE'}
            </div>
            <span>|</span>
            <span>INTERVIEW_ID: {interviewId || 'N/A'}</span>
          </div>
        </div>

        {/* Validation Error Popup */}
        {validationError && (
          <div className="fixed inset-0 flex items-center justify-center bg-black/60 z-50 p-4">
            <div className="bg-slate-900 border border-red-500 rounded-xl shadow-[0_0_20px_rgba(239,68,68,0.3)] p-6 max-w-md text-center w-full">
              <h2 className="text-xl font-bold text-red-500 mb-2">Missing Information</h2>
              <p className="text-[var(--bone)] mb-6 text-sm">{validationError}</p>
              <button
                onClick={() => setValidationError('')}
                className="px-6 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-[var(--radius)] transition-colors w-full"
              >
                OK
              </button>
            </div>
          </div>
        )}

        {/* Dynamic View Rendering Based on Active Stage */}
        <div className="flex-1 overflow-y-auto">
          {activeStage === 'sourcing' && (
            <PipelineDashboardView
              goal={goal}
              setGoal={setGoal}
              standard={standard}
              setStandard={setStandard}
              selectedFile={selectedFile}
              setSelectedFile={setSelectedFile}
              running={running}
              handleRunPipeline={handleRunPipeline}
              runResult={runResult}
              candidates={candidates}
              onSelectCandidate={() => setActiveStage('screening')}
              setValidationError={setValidationError}
            />
          )}

          {activeStage === 'screening' && (
            <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
               <div className="panel p-8 text-center bg-[var(--panel)]">
                 <h2 className="font-display text-2xl font-bold text-[var(--tape)] mb-4">SCREENING ROOM</h2>
                 <p className="text-[var(--mute)] mb-6">Interactive candidate screening and resume parsing operations.</p>
                 <div className="flex justify-center gap-4">
                   <button onClick={() => setActiveStage('sourcing')} className="px-4 py-2 border border-slate-700 rounded text-xs font-mono hover:bg-slate-800 transition">BACK TO SOURCING</button>
                   <button onClick={() => setActiveStage('scheduling')} className="px-4 py-2 bg-[var(--tape)] text-[var(--ink)] font-bold rounded text-xs font-mono hover:bg-[#e6ff00] transition shadow-[0_0_12px_rgba(204,255,0,0.3)]">PROCEED TO SCHEDULING</button>
                 </div>
               </div>
            </div>
          )}

          {activeStage === 'scheduling' && (
            <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
               <div className="panel p-8 text-center bg-[var(--panel)]">
                 <h2 className="font-display text-2xl font-bold text-[var(--tape)] mb-4">SCHEDULING ROOM</h2>
                 <p className="text-[var(--mute)] mb-6">Demonstrating automated mail sending and calendar invites.</p>
                 <div className="flex justify-center gap-4">
                   <button onClick={() => setActiveStage('screening')} className="px-4 py-2 border border-slate-700 rounded text-xs font-mono hover:bg-slate-800 transition">BACK TO SCREENING</button>
                   <button onClick={() => setActiveStage('interview')} className="px-4 py-2 bg-[var(--tape)] text-[var(--ink)] font-bold rounded text-xs font-mono hover:bg-[#e6ff00] transition shadow-[0_0_12px_rgba(204,255,0,0.3)]">SEND INVITES & ENTER INTERVIEW ROOM</button>
                 </div>
               </div>
            </div>
          )}

          {activeStage === 'interview' && (
            <div className="max-w-7xl mx-auto p-4 sm:p-6 space-y-6">
               <div className="panel p-8 text-center bg-[var(--panel)]">
                 <h2 className="font-display text-2xl font-bold text-[var(--signal)] mb-4">INTERVIEW ROOM</h2>
                 <p className="text-[var(--mute)] mb-6">Access the live interview room. Note: In a real scenario, this would route to a full-screen room.</p>
                 <div className="flex justify-center gap-4">
                   <button onClick={() => setActiveStage('scheduling')} className="px-4 py-2 border border-slate-700 rounded text-xs font-mono hover:bg-slate-800 transition">BACK TO SCHEDULING</button>
                   <button onClick={() => setActiveStage('eval')} className="px-4 py-2 bg-[var(--signal)] text-[var(--ink)] font-bold rounded text-xs font-mono hover:bg-[#33f3ff] transition shadow-[0_0_12px_rgba(0,240,255,0.3)]">COMPLETE & GO TO DEBRIEF</button>
                 </div>
               </div>
            </div>
          )}

          {activeStage === 'eval' && (
            <div className="max-w-7xl mx-auto p-4 sm:p-6">
              <HREvaluationDashboard interviewId={interviewId} />
            </div>
          )}

          {activeStage === 'scorecard' && (
            <div className="max-w-7xl mx-auto p-4 sm:p-6 grid grid-cols-1 xl:grid-cols-2 gap-6">
              <FairnessHeatmap roleId={roleId} />
              <ScorecardView supabase={supabase} interviewId={interviewId} />
            </div>
          )}
        </div>

      </main>
    </div>
  );
}

export default App;
