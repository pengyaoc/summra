"""Tests for the LLM-call audit log written by
SummaryGenerator._persist_raw_llm_response and the
_generate_content_with_fallback wrapper.

Goal: every LLM call must be reproducible from the captured JSON — the file
must include both the full input (prompt + sampling config + config_key) and
the full output (text + finish_reason + model + safety info if available), or
in the failure case, the exception details.
"""

from pathlib import Path
import json

import pytest

from scripts.content.generate_summaries import SummaryGenerator


@pytest.fixture
def generator():
    return SummaryGenerator(api_key="dummy")


@pytest.fixture
def captured_log_dir(tmp_path, monkeypatch):
    """Redirect data/llm_responses/ to a tmp_path for each test."""
    target = tmp_path / "llm_responses"
    target.mkdir()
    monkeypatch.setattr(
        "scripts.content.generate_summaries.SummaryGenerator._llm_log_dir",
        lambda self: target,
        raising=False,
    )
    return target


def _read_only_log(log_dir: Path) -> dict:
    files = sorted(log_dir.glob("*.json"))
    assert len(files) == 1, f"expected exactly 1 log file, got {len(files)}: {files}"
    return json.loads(files[0].read_text())


# --- Success-path: log must include input + output + replay parameters -----

def test_successful_call_log_includes_prompt(generator, captured_log_dir):
    class FakeResp:
        text = "### MEDIUM SUMMARY\n\nbody\n"
        candidates = []

    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="THE PROMPT GOES HERE",
        log_label="combined-summary API call",
        gen_config={"temperature": 0.7, "max_output_tokens": 4096},
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert payload["prompt"] == "THE PROMPT GOES HERE"


def test_successful_call_log_includes_response_text(generator, captured_log_dir):
    class FakeResp:
        text = "### MEDIUM SUMMARY\n\nbody of medium\n"
        candidates = []

    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="prompt",
        log_label="combined-summary API call",
        gen_config=None,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert payload["raw_text"] == "### MEDIUM SUMMARY\n\nbody of medium\n"


def test_successful_call_log_includes_model_and_config_key(generator, captured_log_dir):
    class FakeResp:
        text = "ok"
        candidates = []

    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="prompt",
        log_label="combined-summary API call",
        gen_config=None,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert payload["used_model"] == "gemini-3.5-flash"
    assert payload["config_key"] == "combined"


def test_successful_call_log_includes_gen_config(generator, captured_log_dir):
    """gen_config must be persisted so sampling settings are replayable."""
    class FakeResp:
        text = "ok"
        candidates = []

    gen_cfg = {"temperature": 0.3, "top_p": 0.9, "max_output_tokens": 8192}
    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="prompt",
        log_label="combined-summary API call",
        gen_config=gen_cfg,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert "gen_config" in payload
    # Serialized to string or dict — both fine as long as it round-trips
    serialized = payload["gen_config"]
    if isinstance(serialized, dict):
        assert serialized["temperature"] == 0.3
        assert serialized["top_p"] == 0.9
    else:
        assert "0.3" in str(serialized)
        assert "0.9" in str(serialized)


def test_successful_call_log_includes_finish_reason(generator, captured_log_dir):
    class FakeCandidate:
        finish_reason = "STOP"
    class FakeResp:
        text = "ok"
        candidates = [FakeCandidate()]

    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="prompt",
        log_label="combined-summary API call",
        gen_config=None,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert "STOP" in str(payload["finish_reason"])


def test_successful_call_log_marks_status_ok(generator, captured_log_dir):
    """status field lets log consumers filter ok vs error without parsing."""
    class FakeResp:
        text = "ok"
        candidates = []

    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents="prompt",
        log_label="combined-summary API call",
        gen_config=None,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert payload["status"] == "ok"


# --- Failure-path: failed calls must also produce a log entry --------------

def test_failed_call_writes_log_with_error_details(generator, captured_log_dir):
    """When an LLM call raises after the retry/fallback chain exhausts, the
    failure must still be captured: prompt, config_key, gen_config, model
    attempted, error class, and error message."""
    err = RuntimeError("400 FAILED_PRECONDITION. Precondition check failed.")
    generator._persist_raw_llm_error(
        err,
        attempted_models=["gemini-3.5-flash", "gemini-3-flash-preview"],
        contents="THE PROMPT",
        log_label="combined-summary API call",
        gen_config={"temperature": 0.5},
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    assert payload["status"] == "error"
    assert payload["prompt"] == "THE PROMPT"
    assert payload["config_key"] == "combined"
    assert payload["attempted_models"] == [
        "gemini-3.5-flash", "gemini-3-flash-preview"
    ]
    assert payload["error_class"] == "RuntimeError"
    assert "FAILED_PRECONDITION" in payload["error_message"]


# --- Multimodal / non-string contents are not lost ------------------------

def test_non_string_contents_serialized_not_dropped(generator, captured_log_dir):
    """If contents is a list (multimodal or chat history), it must serialize
    to something inspectable, not be silently dropped."""
    class FakeResp:
        text = "ok"
        candidates = []

    multimodal = [
        {"role": "user", "parts": [{"text": "hello"}, {"image": "ref_bytes"}]},
    ]
    generator._persist_raw_llm_response(
        FakeResp(),
        used_model="gemini-3.5-flash",
        contents=multimodal,
        log_label="multimodal call",
        gen_config=None,
        config_key="combined",
    )
    payload = _read_only_log(captured_log_dir)
    p = payload["prompt"]
    p_repr = json.dumps(p) if not isinstance(p, str) else p
    assert "hello" in p_repr
    assert "image" in p_repr  # the multimodal part is not silently dropped
