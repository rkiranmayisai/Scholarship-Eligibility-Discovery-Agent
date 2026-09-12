"""
Optional LLM client.

The agents in this system are built so that their REASONING (rule
evaluation, scoring, ranking, planning) is deterministic and does not
require an LLM at all -- this keeps the hackathon demo fully working
offline / without API keys, and makes the eligibility decisions
auditable rather than hallucinated.

Where natural language is genuinely useful (parsing free-text profile
input, and the conversational chat assistant), we call an LLM IF an
API key is configured, and fall back to a lightweight rule-based /
regex implementation otherwise. Either path returns the same
structured shape, so the rest of the pipeline never needs to know
which one ran.

Supported providers (set LLM_PROVIDER in .env): "openai", "gemini", "none".
"""
import os
import json

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


def llm_available() -> bool:
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        return True
    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        return True
    return False


def call_llm(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    """
    Thin wrapper. Returns raw text. Raises if no provider configured --
    callers should always check llm_available() first and have a
    deterministic fallback ready, per the hackathon requirement that
    the app must work even without live API access.
    """
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY:
        from openai import OpenAI
        client = OpenAI(api_key=OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"} if json_mode else None,
        )
        return resp.choices[0].message.content

    if LLM_PROVIDER == "gemini" and GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))
        resp = model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        return resp.text

    raise RuntimeError("No LLM provider configured")
