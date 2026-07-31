import sys
import os

sys.path.insert(0, os.path.abspath("."))
from app.config import get_settings
from openai import OpenAI

settings = get_settings()
client = OpenAI(
    api_key=settings.GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)
try:
    models = client.models.list()
    print([m.id for m in models.data if "embed" in m.id.lower() or "text" in m.id.lower()])
except Exception as e:
    print(e)
