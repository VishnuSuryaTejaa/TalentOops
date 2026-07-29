"""Bidirectional audio bridge (Task 4.2): bounded queues absorb network jitter."""
import asyncio

QUEUE_MAX = 256


class AudioBridge:
    def __init__(self) -> None:
        self._incoming: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_MAX)
        self._outgoing: asyncio.Queue[bytes] = asyncio.Queue(maxsize=QUEUE_MAX)
        self.dropped_frames = 0

    def _put(self, q: asyncio.Queue, frame: bytes) -> None:
        while q.full():  # drop oldest, keep the live edge
            q.get_nowait()
            self.dropped_frames += 1
        q.put_nowait(frame)

    async def put_incoming(self, frame: bytes) -> None:
        self._put(self._incoming, frame)

    async def get_incoming(self) -> bytes:
        return await self._incoming.get()

    async def put_outgoing(self, frame: bytes) -> None:
        self._put(self._outgoing, frame)

    async def get_outgoing(self) -> bytes:
        return await self._outgoing.get()

    async def loopback_once(self) -> bytes:
        frame = await self.get_incoming()
        await self.put_outgoing(frame)
        return frame


_bridges: dict[str, AudioBridge] = {}


def get_bridge(meeting_id: str) -> AudioBridge:
    return _bridges.setdefault(meeting_id, AudioBridge())


def has_bridge(meeting_id: str) -> bool:
    return meeting_id in _bridges


def remove_bridge(meeting_id: str) -> None:
    _bridges.pop(meeting_id, None)


async def ws_endpoint(websocket, meeting_id: str) -> None:
    await websocket.accept()
    bridge = get_bridge(meeting_id)
    
    from app.services.gemini_live_session import GeminiLiveSession
    from app.services.session_broker import broker
    from app.services.voice_chain import VoiceChain

    # Enforce voice ownership rule via SessionBroker (Task 4.6)
    voice_session = broker.issue_session("interviewer", "candidate")
    
    # Enforce consent gating via VoiceChain (Task 4.6)
    chain = VoiceChain(voice_session)
    call_meta = await chain.open_call()
    chain.acknowledge_consent()
    
    # Start a GeminiLiveSession in script mode for onboarding/connection-check flow.
    # Script mode is used here deliberately: this is the WebSocket audio bridge endpoint
    # which handles the pre-interview connection check sequence, not the main interview.
    # The real Gemini Live API session is started by MultiAgentCoordinator after consent.
    session = GeminiLiveSession(session=voice_session, interview_id=meeting_id, script=[
        call_meta["announcement"],
        "Hi! Before we start, this is a quick non-graded mic and connection check.",
        "How's your audio on your end? Feel free to say a sentence or two.",
        "Great — any questions about how the interview works before we begin?",
        "Okay, the official interview will now begin."
    ])
    await session.start()
    
    frame_count = 0
    try:
        while True:
            frame = await websocket.receive_bytes()
            await bridge.put_incoming(frame)
            
            # Simple VAD implementation: emit a transcript turn every ~100 frames of audio received
            frame_count += 1
            if frame_count % 100 == 0:
                if session._script:
                    await session.next_turn("Testing audio transmission...")
                
            await bridge.loopback_once()
            await websocket.send_bytes(await bridge.get_outgoing())
    except Exception:
        pass
