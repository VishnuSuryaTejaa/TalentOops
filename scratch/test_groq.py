import asyncio
from app.services.llm_clients import groq_chat
import logging

logging.basicConfig(level=logging.INFO)

async def main():
    messages = [
        {"role": "system", "content": "You are an interviewer. Ask a short question."},
        {"role": "user", "content": "Hello"}
    ]
    try:
        response = await groq_chat(messages, json_mode=True, max_tokens=100, temperature=0.9)
        print("Response:", response)
    except Exception as e:
        print("Error:", type(e), e)
        if hasattr(e, 'response'):
            print("Response:", e.response.text)

if __name__ == "__main__":
    asyncio.run(main())
