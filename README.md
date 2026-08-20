# TalentOps 🎯

An autonomous, AI-driven recruitment and multimodal candidate evaluation platform built from the ground up to revolutionize the hiring lifecycle.

**Created and maintained by [VishnuSuryaTejaa](https://github.com/VishnuSuryaTejaa)**

---

## 🚀 Overview

TalentOps is an end-to-end recruitment platform that leverages a multi-agent system to handle the entire hiring process—from resume parsing and candidate screening to autonomous oral interviews and final HR evaluations. 

By utilizing advanced Large Language Models (LLMs), a highly tuned state machine (FSM), and real-time WebRTC audio processing, TalentOps conducts technical and behavioral interviews on behalf of the company, eliminating bias and accelerating the hiring pipeline.

## 🧠 Multi-Agent Architecture

The core of TalentOps is its robust, hierarchical agent framework built on Python and FastAPI.

- **Manager Agent**: The central orchestrator. It dispatches tasks, collects raw evaluation data, and synthesizes executive candidate reports.
- **Resume Screening & Parser Agent**: Ingests candidate resumes (PDF/Docx), parses text, and matches profile vectors against Job Description rubrics.
- **Interviewer Agent**: The candidate-facing bot. Utilizes a Finite State Machine (FSM) to conduct oral interviews over WebRTC, adapting questions dynamically based on the candidate's answers.
- **Evaluator Agent**: Post-processes the interview transcripts, grades responses against predefined competencies, and calculates behavioral metrics and fairness scores.
- **HR Debrief Agent**: Conducts interactive debriefing sessions with human HR managers to provide deep-dive insights on the candidate's performance.

## 🛠️ Tech Stack

### Backend & AI Layer
- **Python / FastAPI**: High-performance asynchronous backend API.
- **LangChain / LangGraph**: Powers the multi-agent coordination and state-machine transitions.
- **Groq & Gemini**: Extremely low-latency LLM inference and multimodal processing.
- **Supabase**: PostgreSQL database and pgvector for candidate profile embeddings and vector search.
- **WebRTC / WebSockets**: Real-time bi-directional audio streaming for live interviews.

### Frontend
- **React 19 & Vite**: Lightning-fast, modern frontend framework.
- **Tailwind CSS v4**: Utility-first CSS for sleek, responsive UI components.
- **Recharts**: For rendering beautiful fairness heatmaps and evaluation dashboards.

## 🌐 Live Demo

- **Frontend**: [TalentOps Frontend (Vercel)](https://talent-oops.vercel.app/)
- **Backend API**: [TalentOps Backend (Render)](https://talentoops-backend.onrender.com)

## 💻 Local Development

### 1. Clone the repository
```bash
git clone https://github.com/VishnuSuryaTejaa/TalentOops.git
cd TalentOops
```

### 2. Backend Setup
Create a `.env` file based on `.env.example`, then start the FastAPI server:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
*The backend runs at `http://localhost:8000`*

### 3. Frontend Setup
In a new terminal window:
```bash
cd frontend
npm install
npm run dev
```
*The frontend runs at `http://localhost:5173`*

## 📝 License & Copyright

All rights reserved. Built with ❤️ by **VishnuSuryaTejaa**.
