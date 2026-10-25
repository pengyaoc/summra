"""Tests for scripts/lib/llm.py — the shared Gemini client factory that
replaces 8 scripts' individually duplicated genai.Client(api_key=...) construction.
"""
import pytest

from scripts.lib.llm import get_gemini_client


def test_get_gemini_client_uses_explicit_api_key_over_config():
    client = get_gemini_client(api_key="explicit-test-key")
    assert client is not None


def test_get_gemini_client_raises_when_no_key_available(monkeypatch):
    monkeypatch.setattr("scripts.lib.llm.config.GEMINI_API_KEY", "")
    with pytest.raises(ValueError, match="Gemini API key not found"):
        get_gemini_client()


def test_get_gemini_client_falls_back_to_config_default(monkeypatch):
    monkeypatch.setattr("scripts.lib.llm.config.GEMINI_API_KEY", "from-config")
    client = get_gemini_client()
    assert client is not None
