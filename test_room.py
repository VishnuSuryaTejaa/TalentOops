import sys
import asyncio
sys.path.append("/Users/apple/TalentOops")
from app.rooms.room_manager import room_manager
from app.services.database import db

async def main():
    room = await room_manager.create_room(
        candidate_id="iv-AI-RESUME_SURYA_-_Si_662a71fb",
        interview_id="test-iv-123",
        run_id="test-run",
        metadata={"candidate_email": "test@test.com"}
    )
    print("Created room:", room.room_id)
    # fetch it
    res = await db.query("interview_rooms", room_id=room.room_id)
    print("DB fetch:", res)

if __name__ == "__main__":
    asyncio.run(main())
