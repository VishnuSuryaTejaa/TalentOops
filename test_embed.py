import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.abspath("."))

from app.config import get_settings
from openai import OpenAI

settings = get_settings()
client = OpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

for model in ["nomic-embed-text-v1_5", "text-embedding-3-small"]:
    try:
        resp = client.embeddings.create(
            model=model,
            input="hello world"
        )
        print(f"{model} dim:", len(resp.data[0].embedding))
    except Exception as e:
        print(f"{model} err:", e)
