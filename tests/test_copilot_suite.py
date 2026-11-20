# -*- coding: utf-8 -*-
import sys
import asyncio
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.copilot import (
    extract_json_object,
    resolve_voice_name,
    parse_segment_id,
    process_copilot_command
)
from starlette.testclient import TestClient
from web.app import app, JOBS

client = TestClient(app)

def test_resolve_voice_name():
    assert resolve_voice_name("Jenny") == "en-US-JennyNeural"
    assert resolve_voice_name("মেয়ে") == "en-US-JennyNeural"
    assert resolve_voice_name("female") == "en-US-JennyNeural"
    assert resolve_voice_name("Ryan") == "en-GB-RyanNeural"
    assert resolve_voice_name("British") == "en-GB-RyanNeural"
    assert resolve_voice_name("male") == "en-US-ChristopherNeural"
    assert resolve_voice_name("Guy") == "en-US-GuyNeural"
    print("PASS: Voice name resolution works for all English & Bengali natural terms.")

def test_parse_segment_id():
    assert parse_segment_id(0) == 0
    assert parse_segment_id("0") == 0
    assert parse_segment_id("line 3") == 3
    assert parse_segment_id("#5") == 5
    assert parse_segment_id(None) is None
    print("PASS: Segment ID parsing handles numbers, strings, and #tags.")

def test_missing_api_keys_graceful_handling():
    # When keys are missing, process_copilot_command should return a helpful message, not crash
    from config import Settings
    old_gemini = Settings.get_gemini_api_key()
    old_groq = Settings.get_groq_api_key()
    try:
        import os
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["GROQ_API_KEY"] = ""
        res = asyncio.run(process_copilot_command("hello", {}))
        assert res["action"] == "error"
        assert "API Key" in res["reply"]
        print("PASS: Missing API key handled with friendly message.")
    finally:
        import os
        os.environ["GEMINI_API_KEY"] = old_gemini
        os.environ["GROQ_API_KEY"] = old_groq

def test_chat_endpoint_validation():
    # Test 404 on non-existent job
    res = client.post("/api/chat", json={"job_id": "non_existent_123", "message": "hello"})
    assert res.status_code == 404
    print("PASS: Chat endpoint rejects invalid job ID.")

    # Test 400 on incomplete job
    JOBS["test_job_pending"] = {"status": "processing"}
    res2 = client.post("/api/chat", json={"job_id": "test_job_pending", "message": "hello"})
    assert res2.status_code == 400
    print("PASS: Chat endpoint protects against editing while job is still processing.")

def test_general_chat_without_job():
    res = client.post("/api/chat", json={"message": "হ্যালো, কোন ভয়েসটা ভালো?"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "reply" in data
    print("PASS: General chat without job works seamlessly.")

if __name__ == "__main__":
    print("\n--- Running Deep Copilot Test Suite ---")
    test_resolve_voice_name()
    test_parse_segment_id()
    test_missing_api_keys_graceful_handling()
    test_chat_endpoint_validation()
    test_general_chat_without_job()
    print("--- ALL DEEP COPILOT TESTS PASSED (100% SUCCESS) ---")
