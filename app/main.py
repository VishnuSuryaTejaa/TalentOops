import re
from datetime import datetime, timezone
from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from app.config import settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    from app.services.logging import (
        configure_logging,
        RequestLoggingMiddleware,
        ErrorLoggingMiddleware
    )

    # Configure logging
    logger = configure_logging()
    logger.info("Creating TalentOps application")

    app = FastAPI(title="TalentOps")



    # Apply middleware for CORS, gzip compression, and logging
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # Add logging middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ErrorLoggingMiddleware)

    logger.info("Application middleware configured")

    from fastapi import Request, Form, File, UploadFile
    from pydantic import BaseModel
    from typing import Optional, List, Dict, Any

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint."""
        logger.info("Health check requested")
        from app.graph.state import SUB_AGENTS
        nodes = ["manager"] + SUB_AGENTS
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "supabase_configured": settings.supabase_configured,
            "nodes": nodes,
            "supervisor_nodes": nodes,
        }

    from fastapi.responses import RedirectResponse

    @app.get("/interview/{room_id}")
    async def redirect_to_frontend_interview_room(room_id: str):
        """Redirect backend interview room links to the frontend SPA.

        The React App.jsx handles /interview/{room_id} by rendering <InterviewRoom />.
        This redirect ensures links generated with ROOM_BASE_URL=http://localhost:8000
        still work by bouncing to the frontend at localhost:5173.
        """
        frontend_url = settings.ROOM_BASE_URL.rstrip("/")
        return RedirectResponse(url=f"{frontend_url}/interview/{room_id}", status_code=302)

    @app.api_route("/rest/v1/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    async def supabase_rest_fallback(path: str):
        """Fallback for Supabase PostgREST calls accidentally hitting FastAPI backend."""
        raise HTTPException(status_code=404, detail="Supabase API requests should not hit the backend.")



    class RunRequest(BaseModel):
        goal: str
        standard: Optional[str] = None
        corpus: Optional[List[Dict[str, Any]]] = None

    class EmailQueryRequest(BaseModel):
        role_id: str
        from_email: str
        subject: Optional[str] = ""

    class DebriefDeployRequest(BaseModel):
        run_id: str

    @app.post("/run")
    async def run_pipeline_endpoint(
        request: Request,
        goal: Optional[str] = Form(None),
        standard: Optional[str] = Form(None),
        resume: Optional[UploadFile] = File(None),
    ) -> dict:
        import os
        import uuid
        from app.graph.supervisor import run_pipeline

        corpus = []
        req_goal = goal
        req_standard = standard

        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                body = await request.json()
                req_goal = body.get("goal")
                req_standard = body.get("standard")
                if body.get("corpus"):
                    corpus.extend(body.get("corpus"))
            except Exception:
                pass

        if not req_goal:
            req_goal = "Hire a senior backend engineer"

        if resume:
            from fastapi import HTTPException
            from app.services.parser import parse_resume_bytes, ResumeParseError

            os.makedirs("temp_uploads", exist_ok=True)
            filename = os.path.basename(resume.filename or "resume.pdf")
            content = await resume.read()
            
            try:
                parse_resume_bytes(content, file_name=filename)
            except ResumeParseError as e:
                raise HTTPException(status_code=400, detail=str(e))

            path = os.path.join("temp_uploads", f"{uuid.uuid4().hex}_{filename}")
            with open(path, "wb") as f:
                f.write(content)
            corpus.append({"id": filename.rsplit('.', 1)[0], "pdf_path": path})

        if not corpus and os.path.exists("temp_uploads"):
            for fname in sorted(os.listdir("temp_uploads"), reverse=True):
                fpath = os.path.join("temp_uploads", fname)
                if os.path.isfile(fpath) and not fname.startswith("."):
                    corpus.append({"id": fname.rsplit(".", 1)[0], "pdf_path": fpath})

        logger.info("Starting pipeline run for goal: %s", req_goal)
        return await run_pipeline(goal=req_goal, standard=req_standard, corpus=corpus if corpus else None)

    @app.post("/manager_debrief/deploy")
    async def manager_debrief_deploy_endpoint(req: DebriefDeployRequest) -> dict:
        from app.agents.manager_debrief import create_manager_debrief_session
        return await create_manager_debrief_session(
            interview_id=req.run_id,
            run_id=req.run_id,
            final_state={"goal": "Hiring Run", "run_id": req.run_id}
        )

    class UploadResumeRequest(BaseModel):
        file_name: str
        content: str

    @app.post("/upload_resume")
    async def upload_resume_endpoint(req: UploadResumeRequest) -> dict:
        import os
        import uuid
        import base64
        from fastapi import HTTPException
        from app.services.parser import parse_resume_bytes, ResumeParseError

        os.makedirs("temp_uploads", exist_ok=True)
        filename = os.path.basename(req.file_name or "resume.txt")
        
        content_str = req.content or ""
        if "," in content_str:
            content_str = content_str.split(",", 1)[1]

        try:
            raw_bytes = base64.b64decode(content_str)
        except Exception:
            raw_bytes = req.content.encode("utf-8")

        if not raw_bytes.startswith(b"%PDF") and req.content.startswith("%PDF"):
            raw_bytes = req.content.encode("utf-8")

        try:
            parsed = parse_resume_bytes(raw_bytes, file_name=filename)
        except ResumeParseError as e:
            raise HTTPException(status_code=400, detail=str(e))

        path = os.path.join("temp_uploads", f"{uuid.uuid4().hex}_{filename}")
        with open(path, "wb") as f:
            f.write(raw_bytes)

        from app.services.parser import extract_candidate_metadata, clean_candidate_name
        meta = extract_candidate_metadata(parsed.raw_text, file_name=filename)
        cand_name = meta.get("full_name") or parsed.candidate_name or clean_candidate_name(filename) or "Candidate"
        cand_email = meta.get("email") or parsed.email or ""

        # Unique, collision-free candidate ID
        clean_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", filename.rsplit(".", 1)[0])[:20]
        cand_id = f"{clean_prefix}_{uuid.uuid4().hex[:8]}"

        from app.services.database import db
        try:
            await db.insert("candidates", {
                "id": cand_id,
                "name": cand_name,
                "email": cand_email if cand_email else None,
                "phone": parsed.phone or "",
                "summary": parsed.summary or "",
                "skills": parsed.skills or [],
                "experience": [e.model_dump() for e in parsed.experience] if parsed.experience else [],
                "education": [e.model_dump() for e in parsed.education] if parsed.education else [],
                "raw_text": parsed.raw_text,
                "resume_path": path,
            })

            for proj in parsed.projects:
                try:
                    await db.insert("projects", {
                        "candidate_id": cand_id,
                        "title": proj.title,
                        "description": proj.description,
                        "technologies": proj.technologies,
                        "url": proj.url,
                    })
                except Exception as proj_exc:
                    logger.warning("Supabase insert project notice: %s", proj_exc)

        except Exception as exc:
            logger.warning("Supabase insert candidate notice: %s", exc)

        return {
            "status": "uploaded",
            "path": path,
            "candidate_id": cand_id,
            "candidate_name": cand_name,
            "email": cand_email,
            "projects_count": len(parsed.projects),
        }

    class ScheduleInterviewRequest(BaseModel):
        candidate_id: str
        role_id: str
        slot_iso: str
        timezone: Optional[str] = "UTC"

    @app.post("/schedule_interview")
    async def schedule_interview_endpoint(req: ScheduleInterviewRequest) -> dict:
        from app.services.interview_scheduler import schedule_candidate_interview
        from fastapi import HTTPException
        try:
            return await schedule_candidate_interview(
                candidate_id=req.candidate_id,
                role_id=req.role_id,
                slot_iso=req.slot_iso,
                timezone_str=req.timezone or "UTC",
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class StartRoomSessionRequest(BaseModel):
        candidate_id: str
        role_id: str
        room_id: str
        consent_response: Optional[str] = "Yes, I consent to the recording."
        candidate_turns: Optional[List[str]] = None

    @app.post("/start_meet_session")
    async def start_meet_session_endpoint(req: StartRoomSessionRequest) -> dict:
        from app.services.multi_agent_coordinator import MultiAgentCoordinator
        from fastapi import HTTPException
        try:
            coord = MultiAgentCoordinator(
                candidate_id=req.candidate_id,
                role_id=req.role_id,
                room_id=req.room_id,
            )
            return await coord.run_session(
                consent_response_text=req.consent_response or "Yes, I consent to the recording.",
                candidate_turns=req.candidate_turns,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class OralTurnRequest(BaseModel):
        session_id: str
        candidate_id: str
        role_id: str
        candidate_text: Optional[str] = None
        candidate_audio_b64: Optional[str] = None

    @app.post("/oral_interview/turn")
    async def oral_interview_turn_endpoint(req: OralTurnRequest) -> dict:
        from app.agents.oral_interview_agent import OralInterviewAgent
        from fastapi import HTTPException
        try:
            agent = OralInterviewAgent()
            return await agent.process_turn(
                session_id=req.session_id,
                candidate_id=req.candidate_id,
                role_id=req.role_id,
                candidate_text=req.candidate_text,
                candidate_audio_b64=req.candidate_audio_b64,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/interviews/{interview_id}/evaluation")
    async def get_interview_evaluation(
        interview_id: str,
        q: Optional[str] = None,
        x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    ) -> dict:
        from fastapi import HTTPException
        from app.services.database import db
        if not x_user_role or str(x_user_role).lower() != "hr":
            raise HTTPException(status_code=403, detail="Access denied: HR role permission required.")

        records = await db.query("scorecards", interview_id=interview_id)
        if not records:
            records = await db.query("scorecards", candidate_id=interview_id)

        target_room_id = interview_id
        target_cand_id = interview_id
        target_interview_id = interview_id
        rubric = {}

        # Resolve real IDs from interview_rooms if direct query returned no records
        if not records:
            try:
                rooms = await db.query("interview_rooms", room_id=interview_id)
                if not rooms:
                    rooms = await db.query("interview_rooms", interview_id=interview_id)
                if rooms:
                    r = rooms[0]
                    target_room_id = r.get("room_id") or interview_id
                    target_cand_id = r.get("candidate_id") or interview_id
                    target_interview_id = r.get("interview_id") or interview_id
                    rubric = (r.get("metadata") or {}).get("rubric") or {}

                    if target_interview_id:
                        records = await db.query("scorecards", interview_id=target_interview_id)
                    if not records and target_room_id:
                        records = await db.query("scorecards", interview_id=target_room_id)
                    if not records and target_cand_id:
                        records = await db.query("scorecards", candidate_id=target_cand_id)
            except Exception as exc:
                logger.warning("Error resolving room for evaluation %s: %s", interview_id, exc)

        # On-demand evaluation fallback: generate scorecard on-the-fly if transcript exists
        if not records:
            logger.info("No scorecard found for %s — running on-demand evaluation fallback", interview_id)
            try:
                if target_cand_id == interview_id:
                    cands = await db.query("candidates", id=interview_id)
                    if cands:
                        target_cand_id = cands[0].get("id", interview_id)

                qa_logs = await db.query("interview_qa_logs", session_id=target_room_id)
                if not qa_logs:
                    qa_logs = await db.query("interview_qa_logs", session_id=target_interview_id)
                if not qa_logs:
                    qa_logs = await db.query("interview_qa_logs", session_id=interview_id)

                live_turns = []
                if qa_logs:
                    sorted_logs = sorted(qa_logs, key=lambda x: x.get("question_number", 0))
                    for log in sorted_logs:
                        q_t = log.get("question_text", "")
                        c_t = log.get("candidate_answer_transcript", "")
                        if q_t:
                            live_turns.append({"speaker": "interviewer", "text": q_t})
                        if c_t:
                            live_turns.append({"speaker": "candidate", "text": c_t})

                from app.agents.evaluator_agent import EvaluatorAgent
                evaluator = EvaluatorAgent(run_id="run-ondemand-eval")
                eval_payload = await evaluator.evaluate_transcript(
                    interview_id=target_interview_id,
                    candidate_id=target_cand_id,
                    rubric=rubric,
                    transcript_turns=live_turns,
                )
                if eval_payload and isinstance(eval_payload, dict):
                    records = [eval_payload]
            except Exception as eval_err:
                logger.error("On-demand evaluation failed for %s: %s", interview_id, eval_err)

        if not records:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Evaluation report not yet available for this interview. "
                    "The interview may still be in progress or evaluation is pending. "
                    "Please check back in a moment."
                ),
            )

        rec = records[0]

        if "data" in rec and isinstance(rec["data"], dict) and "scorecard" not in rec:
            rec = {**rec, **rec["data"]}

        normalized = {
            "interview_id": rec.get("interview_id", interview_id),
            "candidate_id": rec.get("candidate_id", "Unknown"),
            "scorecard": rec.get("scorecard") or {},
            "behavioral_metrics": rec.get("behavioral_metrics") or {},
            "detailed_competencies": rec.get("detailed_competencies") or [],
            "full_transcript_evaluations": rec.get("full_transcript_evaluations") or [],
            "final_recommendation": rec.get("final_recommendation") or {},
            "scorecard_id": rec.get("scorecard_id") or rec.get("id", ""),
        }
        
        if q:
            q_lower = q.lower()
            filtered_evals = []
            for t in normalized["full_transcript_evaluations"]:
                if (q_lower in str(t.get("question", "")).lower() or
                    q_lower in str(t.get("candidate_answer", "")).lower() or
                    q_lower in str(t.get("evaluator_notes", "")).lower()):
                    filtered_evals.append(t)
            normalized["full_transcript_evaluations"] = filtered_evals
            
        return normalized

    class CreateDebriefRequest(BaseModel):
        interview_id: str
        candidate_id: str = "c-alex"

    class DebriefTurnRequest(BaseModel):
        interview_id: str
        hr_question: str

    @app.post("/api/debrief/create")
    async def create_debrief_endpoint(req: CreateDebriefRequest) -> dict:
        from app.agents.manager_debrief import create_manager_debrief_session
        from fastapi import HTTPException
        try:
            return await create_manager_debrief_session(
                interview_id=req.interview_id,
                candidate_id=req.candidate_id
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/debrief/{interview_id}")
    async def get_debrief_session(
        interview_id: str,
        x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    ) -> dict:
        from fastapi import HTTPException
        from app.services.database import db
        if x_user_role != "hr":
            raise HTTPException(status_code=403, detail="Access denied: HR role permission required.")

        sessions = await db.query("hr_debrief_sessions", interview_id=interview_id)
        if not sessions:
            # Return default debrief session (room_url instead of meet_link)
            return {
                "interview_id": interview_id,
                "candidate_id": "c-alex",
                "room_url": f"http://localhost:8000/interview/debrief-{interview_id[:8]}",
                "status": "Manager Agent Waiting",
                "summary": "Manager Agent ready for HR oral debrief.",
                "knowledge_context": {"candidate_id": "c-alex", "interview_id": interview_id},
            }
        return sessions[0]

    @app.post("/api/debrief/turn")
    async def process_debrief_turn_endpoint(req: DebriefTurnRequest) -> dict:
        from app.agents.manager_debrief import process_hr_debrief_turn
        from fastapi import HTTPException
        try:
            return await process_hr_debrief_turn(
                interview_id=req.interview_id,
                hr_question=req.hr_question
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    class ManagerQueryRequest(BaseModel):
        interview_id: str
        question: str
        role_id: Optional[str] = "role-default"

    @app.post("/manager/query")
    async def manager_query_endpoint(req: ManagerQueryRequest) -> dict:
        from app.agents.manager_agent import ManagerAgent
        from fastapi import HTTPException
        try:
            agent = ManagerAgent(role_id=req.role_id or "role-default")
            return await agent.answer_interview_question(
                interview_id_or_candidate_id=req.interview_id,
                question=req.question
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/query_email")
    async def query_email_endpoint(req: EmailQueryRequest) -> dict:
        from app.services.email_handler import handle_incoming_email
        payload = {"role_id": req.role_id, "from": req.from_email, "subject": req.subject or ""}
        return await handle_incoming_email(payload)

    for name in ("webhooks", "fairness", "interviews", "rooms"):
        try:
            module = __import__(f"app.api.routes.{name}", fromlist=["router"])
            app.include_router(module.router)
        except (ImportError, AttributeError):
            # Also register from app.rooms if not in api.routes
            if name == "rooms":
                try:
                    from app.rooms.router import router as rooms_router
                    app.include_router(rooms_router)
                except ImportError:
                    pass

    # ── WebSocket: interview rooms (primary) ─────────────────────────────────
    try:
        from app.rooms.signaling import room_ws_handler
        from fastapi import WebSocket

        @app.websocket("/ws/room/{room_id}")
        async def room_ws(websocket: WebSocket, room_id: str) -> None:
            await room_ws_handler(websocket, room_id)
    except ImportError:
        pass

    # ── WebSocket: legacy audio bridge (kept for backward compat) ────────────
    try:
        from app.services.audio_bridge import ws_endpoint
        from fastapi import WebSocket, status

        @app.websocket("/ws/audio/{meeting_id}")
        async def audio_ws(websocket: WebSocket, meeting_id: str) -> None:
            await ws_endpoint(websocket, meeting_id)

        @app.websocket("/ws/audio")
        async def audio_ws_fallback(websocket: WebSocket) -> None:
            meeting_id = websocket.query_params.get("meeting_id") or websocket.query_params.get("interview_id")
            if not meeting_id:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Meeting ID required")
                return
            await ws_endpoint(websocket, meeting_id)
    except ImportError:
        pass



    return app


app = create_app()
