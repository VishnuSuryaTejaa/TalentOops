# TalentOps — Multi-Phase System Upgrade Blueprint & TDD Roadmap

## 1. Multi-Phase Upgrade Blueprint Roadmap

### 🚀 Phase 1: Workflow State Machine & Resume Screening Upgrade
- **Objective**: Formalize the explicit 6-stage recruitment lifecycle in `PipelineState` and enforce strict upward-only envelope reporting for the Resume Screening Subagent.
- **Key Deliverables**:
  1. Add `WorkflowStage` enum (`APPLICATION_RECEIVED`, `SCREENING`, `SCHEDULING`, `INTERVIEWING`, `EVALUATION`, `HR_DEBRIEF`) to `app/graph/state.py`.
  2. Refactor `manager_node` in `app/graph/nodes.py` to route based on `state["stage"]` rather than array index.
  3. Encapsulate `sourcing` and `screening` under the `SCREENING` stage, guaranteeing that candidate ranking results flow exclusively to `manager`.

### 🎙️ Phase 2: Candidate GMeet Audio Bot & Interviewer FSM Alignment
- **Objective**: Harden the Candidate-Facing Interviewer Subagent, ensuring PCM audio transport over WebSockets and post-call raw transcript dispatch upward to Manager Agent.
- **Key Deliverables**:
  1. Validate 8-stage FSM state transitions (`SANDBOX` $\rightarrow$ `POST_CALL`) in `app/agents/interviewer_fsm.py`.
  2. Ensure raw transcript and PCM audio logs emit an Envelope with `recipient="manager"` upon call completion.

### 📊 Phase 3: Evaluation Engine & Manager Debrief Session
- **Objective**: Formalize the internal Candidate Evaluation Subagent and the Manager AI Agent verbal debriefing session with Human HR.
- **Key Deliverables**:
  1. Isolate transcript evaluation into a dedicated `EVALUATION` stage node.
  2. Guarantee that Human HR interacts exclusively with the Manager Agent via the dashboard and dedicated Manager Debrief Google Meet call.

---

## 2. Phase 1 File Modification Tree

```text
app/
├── graph/
│   ├── state.py         # [MODIFY] Add WorkflowStage enum & stage field to PipelineState
│   ├── nodes.py         # [MODIFY] Update manager_node & worker nodes for stage-based routing
│   └── supervisor.py    # [MODIFY] Log stage transitions in run_pipeline()
├── agents/
│   ├── manager_agent.py # [MODIFY] Add stage transition decision logic
│   └── screening.py     # [MODIFY] Ensure output envelope recipient is strictly "manager"
└── tests/
    └── test_suite.py    # [MODIFY] Add tests verifying explicit 6-stage lifecycle transitions
```

---

## 3. TDD Workflow & Quality Gates

To ensure system reliability, all upgrades currently rely on manual testing until a test suite is established:

1. **Local Setup**:
   - Ensure the backend and frontend can run locally without errors before implementing code changes.
2. **Implementation**:
   - Modify target files to implement the required changes.
3. **Manual Verification**:
   - Manually verify that the changes work as intended in the local environment.
   - Execute `delivery-gate` checks: compile clean frontend bundle (`npm run build`), verify 0 lint errors, and confirm no hardcoded secrets exist.
