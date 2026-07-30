import json
import logging
from typing import Any

from app.services.llm_clients import groq_chat, openrouter_chat

logger = logging.getLogger("talentops.parser_agent")

PARSER_SYSTEM_PROMPT = """\
=== ROLE & OPERATIONAL BOUNDARY ===
You are the Resume Parser AI Agent for TalentOps.
Your task is to take unstructured resume text and output a highly structured JSON object representing the candidate's professional profile.

=== ANTI-HALLUCINATION RULES ===
- Extract information strictly from the provided resume text.
- Do NOT invent companies, projects, schools, or skills that are not mentioned.
- If a section (e.g., projects, education) is completely missing, return an empty array for that field.

=== STRUCTURING PROJECTS & EDUCATION ===
- CRITICAL: DO NOT group multiple distinct projects into a single project object. 
- CRITICAL: Each distinct project MUST be its own object in the `projects` array with `title`, `description`, `technologies` (list of tech skills used), and `url` (if present).
- If the description of a project is missing, do not hallucinate it. If the text only provides the project name, use the name as title and leave description empty.
- For education, ensure each degree/institution combination is completely separate in the `education` array.

=== OUTPUT FORMAT ===
You must return valid JSON strictly conforming to this schema (do NOT include markdown fences, just the raw JSON):

{
  "summary": "<Candidate's professional summary. Empty string if not present.>",
  "skills": ["<skill1>", "<skill2>"],
  "projects": [
    {
      "title": "<Project title>",
      "description": "<Detailed description of what the candidate built and their role>",
      "technologies": ["<tech1>", "<tech2>"],
      "url": "<Link to the project if present, otherwise empty string>"
    }
  ],
  "experience": [
    {
      "company": "<Company name>",
      "role": "<Job title>",
      "dates": "<Date range>",
      "description": "<Description of responsibilities and achievements>"
    }
  ],
  "education": [
    {
      "degree": "<Degree name, e.g., B.S. Computer Science>",
      "institution": "<University or School name>",
      "year": "<Graduation year or date range>"
    }
  ]
}
"""

def _safe_llm_json(raw: str) -> dict:
    """Parse LLM JSON output, stripping markdown code fences if present."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # strip ```json ... ``` fences
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)

async def parse_resume_with_llm(raw_text: str) -> dict[str, Any]:
    """
    Extract structured resume data using an LLM.
    Uses groq_chat primarily, with fallback to openrouter_chat.
    """
    user_prompt = f"Resume Text:\n{raw_text}\n\nParse the above resume text into the required JSON format."
    
    try:
        raw = await groq_chat(
            messages=[
                {"role": "system", "content": PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            json_mode=True,
            max_tokens=4000,
        )
        return _safe_llm_json(raw)
    except Exception as groq_err:
        logger.warning("parser_agent: groq_chat failed: %s, falling back to openrouter", groq_err)
        try:
            raw = await openrouter_chat(
                messages=[
                    {"role": "system", "content": PARSER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                json_mode=True,
                max_tokens=4000,
            )
            return _safe_llm_json(raw)
        except Exception as or_err:
            logger.error("parser_agent: both LLMs failed. groq: %s | or: %s", groq_err, or_err)
            raise ValueError("Failed to parse resume with LLM") from or_err
