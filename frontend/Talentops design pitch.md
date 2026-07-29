# TalentOps — Design Pitch
### "The Signal Chain" — a control-room interface for a system that listens for a living

---

## 0. The thesis

TalentOps isn't a form-and-table HR tool. It's a pipeline of specialized agents passing a candidate down a chain — sourcing, screening, scheduling, live voice interview, evaluation, debrief — with a machine actually *listening* to a human being at the center of it. The UI should read like the inside of a broadcast control room or a mixing console, not like a generic SaaS dashboard: signal chains, meters, live levels, transcripts assembling in real time. The one thing this product does that almost nothing else does is turn a human voice into a structured, defensible hiring decision. Everything visual should be in service of making *that* moment feel real, precise, and accountable — not decorative.

Avoid the three defaults everyone's shipping right now: cream-background/serif/terracotta, near-black/single-neon-accent, or hairline-rule broadsheet. This uses a different logic entirely: an analog broadcast/tape-deck vocabulary applied to a modern agent pipeline.

---

## 1. Token system

### Color — "Control Room"

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#0B0E14` | Base background — near-black blue, not pure black |
| `--panel` | `#151A24` | Card/panel surface, one step up from ink |
| `--tape` | `#E8A33D` | Primary accent — warm analog amber, VU-meter/tape-reel color. Used for active states, the live signal, primary CTAs |
| `--signal` | `#5FD3C4` | Secondary accent — cool cyan for data/embeddings/similarity, "machine cognition" moments |
| `--alert` | `#FF6B5B` | Escalation, reject, needs-review, error states only — never decorative |
| `--bone` | `#EDE6D9` | Primary text on dark — warm off-white, not pure white |
| `--mute` | `#7C8394` | Secondary text, timestamps, metadata |

Why this palette: amber-on-ink is the color of a tape deck's recording light and a VU meter at rest — it's specific to *this* product's actual mechanism (recording consent, audio capture, live evaluation) rather than borrowed from an unrelated aesthetic. Cyan is reserved exclusively for anything vector/embedding/similarity-related, so a user learns "amber = the live human signal, cyan = the machine's read on it" without being told.

### Type — "Grotesque with a pulse"

- **Display** — [Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque) (variable, wght 200–800, has an `opsz` axis). This is the "crazy font": a humanist grotesque with wonky, slightly organic curves that reads as engineered *and* alive — apt for a machine trying to sound human. Used at large scale (72–140px) for stage names and headlines, tight tracking (-2%), and — see Signature Element below — its optical-size axis is the animation mechanism, not just a static choice.
- **Body** — [IBM Plex Sans](https://fonts.google.com/specimen/IBM+Plex+Sans). Built for a technical company, has real character without being loud, excellent at small sizes for dense dashboard content.
- **Mono / data / transcript** — [IBM Plex Mono](https://fonts.google.com/specimen/IBM+Plex+Mono). Same superfamily as body so it never feels like a bolt-on. Every transcript line, timestamp, `competency_id`, JSON payload, and log line in the product renders in this face — it's literally "the voice of the system typing what it heard."

```css
--font-display: 'Bricolage Grotesque', sans-serif;
--font-body: 'IBM Plex Sans', sans-serif;
--font-mono: 'IBM Plex Mono', monospace;
```

Type scale (rem, 1rem = 16px): `0.75 / 0.875 / 1 / 1.25 / 1.75 / 2.5 / 4 / 6.5`
Display headlines sit at 4–6.5rem, weight 650, `opsz` maxed. Body copy at 1rem/1.25rem, weight 400–450. Mono content at 0.875rem, weight 400, `letter-spacing: 0.01em`.

### Layout — "The signal chain rail"

Unlike a marketing page, TalentOps' stages (Sourcing → Screening → Scheduling → Interview → Evaluation → Debrief) really are an ordered sequence with real state — this is one of the rare cases where a numbered/stepped structural device is earned, not decorative, because it mirrors `WorkflowStage` in the actual state machine.

```
┌─────────────────────────────────────────────────────────────┐
│ ●SOURCING ──○SCREENING ──○SCHEDULING ──○INTERVIEW ──○EVAL ──○DEBRIEF   ← signal chain rail, always visible
├─────────────────────────────────────────────────────────────┤
│  RUN: Hire AI Engineer                          [amber pulse dot = live]
│  ┌──────────────┐  ┌──────────────────────────────┐         │
│  │ candidate     │  │  main panel: contents vary     │       │
│  │ rail (mono)   │  │  by active stage                │       │
│  └──────────────┘  └──────────────────────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

The rail is a horizontal signal path (not a checklist with checkmarks) — each stage is a lit/unlit node connected by a thin conductive line that visibly "carries current" (a slow amber pulse) toward whichever node is active, echoing `determine_next_stage()` in the graph. Completed stages stay lit at low intensity; the active stage pulses; future stages sit dim and unlit. Candidates literally move left to right along this rail as their record advances through the pipeline.

### Signature element — "Waveform → Transcript"

The one thing this page will be remembered for: on the live interview room screen, the candidate's voice renders as a real-time amber waveform along the bottom of the screen. As speech is transcribed, the waveform bars nearest the playhead morph directly into IBM Plex Mono glyphs of the words just spoken — the audio literally dissolves into text as it's understood. This is the actual mechanism of `OralInterviewAgent` (STT converting speech to structured Q&A logs) made visible, not an abstract loading animation. Consent screens use a stilled, single-bar version of the same waveform (amber, unlit) that only starts moving once consent is granted — the waveform *is* the recording indicator, doing double duty as both UI chrome and the literal privacy signal.

---

## 2. Page-by-page

### 2.1 Pipeline Dashboard (run overview)
- Signal chain rail pinned at top, full-width, always visible on scroll.
- Below it: a candidate list rendered like a mixing console channel strip — each candidate is a horizontal "channel" with a small live meter showing their current-stage confidence score (the same 0–1 values already computed by `evaluate_confidence`), amber for above-threshold, alert-coral for `needs_review`.
- Run metadata (goal, standard, started timestamp) in IBM Plex Mono, small, top-left — treated like a tape label, not a page title.

### 2.2 Interview Room (live)
- Full-bleed `--ink` background. Candidate identity reduced to a small mono label, never a large photo/hero — the product's fairness model is about consistent standards, so the design shouldn't visually spotlight identity.
- Center: the FSM's current state (`OPENING`, `PROBING`, `FOLLOWUPS`...) shown as a single large Bricolage Grotesque word, low-key, top-center — this is the only place the raw `InterviewState` enum is surface-level UI copy, and it should read like a broadcast "ON AIR" style state indicator.
- Bottom third: the waveform → transcript signature element, full width.
- No score, no rating, no confidence number visible anywhere on this screen — matches the codebase's own D19 rule that the interviewer never scores. Showing a live number here would misrepresent what's actually happening and should be treated as a hard design constraint, not just a style choice.

### 2.3 Consent screen
- Single centered panel, `--panel` background, generous whitespace — this is the one screen that should feel slow and deliberate rather than dense.
- The stilled waveform bar sits above the consent question, unlit amber (`opacity: 0.3`), with a caption in mono: `RECORDING — NOT STARTED`. On explicit consent, the bar lights to full amber and the caption changes to `RECORDING — LIVE`. No auto-advance, no default-selected button — both Agree/Decline are equal-weight, same size, same visual priority.

### 2.4 Scorecard / Evaluation view
- Competency breakdown as horizontal amber meters (matching the dashboard channel-strip language), each with its `technical_accuracy` value in mono to the right — never obscure the raw number behind a badge or letter grade alone.
- Quotes pulled into evidence appear as mono block excerpts with a thin cyan left-border, visually marking "the machine's evidence" distinctly from prose commentary in Plex Sans.
- `needs_human_review` renders as a persistent alert-coral banner, not a subtle badge — this flag exists specifically to route to a human, so it should be the loudest thing on the page when true.

### 2.5 HR Debrief (voice Q&A with Manager Agent)
- Same room chrome as the interview room (waveform, mono transcript) but in `--signal` cyan instead of amber — visually distinguishes "the machine talking to HR about a candidate" from "the machine talking to a candidate," using the same visual grammar for a different direction of signal flow.

---

## 3. Motion

One orchestrated moment, not scattered effects: the signal-chain rail's current-node pulse (2.4s ease-in-out, opacity 0.4→1→0.4) is the *only* ambient animation running at rest anywhere in the product. Everything else is response to real events — waveform bars react to actual audio amplitude, meters fill on data load, the rail's connecting line animates a single "current flow" pulse the moment a candidate's stage changes. `prefers-reduced-motion` disables the ambient rail pulse and the waveform bar transitions; state changes still happen, just as instant swaps instead of animated ones.

---

## 4. Engineering handoff notes

```css
:root {
  --ink: #0B0E14;
  --panel: #151A24;
  --tape: #E8A33D;
  --signal: #5FD3C4;
  --alert: #FF6B5B;
  --bone: #EDE6D9;
  --mute: #7C8394;

  --font-display: 'Bricolage Grotesque', sans-serif;
  --font-body: 'IBM Plex Sans', sans-serif;
  --font-mono: 'IBM Plex Mono', monospace;

  --radius: 6px;      /* small, consistent — this isn't a soft/rounded brand */
  --space-unit: 8px;  /* 8px base spacing scale */
}
```

- All three fonts are free and self-hostable via Google Fonts — pull the variable Bricolage Grotesque `.woff2` specifically (not static weights) so the `opsz`/`wght` axes are available for the state-label and headline treatments.
- Keep `--radius` small and consistent (6px) everywhere — sharp-ish corners read "instrument panel," not "friendly app." Don't let this drift toward pill-shaped buttons or large rounded cards; that's a different, unrelated aesthetic direction and will undercut the whole thesis.
- Meters/waveform can ship as SVG or Canvas; Canvas is preferable for the live interview waveform for perf reasons given it's updating on real audio amplitude.
- Every mono block (transcript, JSON, `competency_id`, quotes) should share one `<TranscriptBlock>` component so the "machine's own words" visual language stays consistent across dashboard, scorecard, and debrief screens.
- Color usage is a hard rule, not a suggestion: amber = live human signal / primary action, cyan = machine-computed/data, coral = escalation only. Don't reach for coral as a generic "important" color — it's reserved for `needs_human_review`/error states so it keeps its urgency.

---

## 5. What to cut if it's running long

If the developer needs to scope this down for a v1: keep the signal-chain rail and the color/type system non-negotiable — those two things carry the whole identity. The waveform → transcript signature element on the live interview room is the single highest-impact piece to build if only one "wow" moment is affordable; the debrief room's cyan variant can reuse the same component with a palette swap rather than being built separately.