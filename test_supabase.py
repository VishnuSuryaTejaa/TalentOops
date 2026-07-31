import asyncio
from app.services.database import db

async def main():
    try:
        res = await db.query("interview_rooms")
        print("interview_rooms:", len(res))
    except Exception as e:
        print("Error:", e)

    try:
        res = await db.query("candidates")
        print("candidates:", len(res))
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
