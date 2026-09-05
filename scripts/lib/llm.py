"""Shared Gemini client factory for one-off scripts.

Before this, 8 scripts each independently resolved GEMINI_API_KEY (some from
os.getenv only, some from config.GEMINI_API_KEY only, some checking both) and
called `genai.Client(api_key=...)` themselves. Use this instead:

    from scripts.lib.llm import get_gemini_client

    client = get_gemini_client()  # raises ValueError if no key is configured
"""
from google import genai

from backend import config


def get_gemini_client(api_key: str = None) -> genai.Client:
    """A genai.Client for the given (or configured) API key.

    api_key defaults to config.GEMINI_API_KEY (which itself reads
    GEMINI_API_KEY from the environment). Raises ValueError if no key is
    available anywhere — callers should catch this if they want a softer
    failure (print-and-exit, preview mode, etc.) rather than a traceback.
    """
    key = api_key or config.GEMINI_API_KEY
    if not key:
        raise ValueError(
            "Gemini API key not found. Set GEMINI_API_KEY in the environment "
            "or config."
        )
    return genai.Client(api_key=key)
