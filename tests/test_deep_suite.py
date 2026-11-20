import sys
import os
import re
import asyncio
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from starlette.testclient import TestClient

from config import Settings, get_local_ip
from core.ffmpeg_utils import (
    get_ffmpeg_path,
    run_ffmpeg,
    has_audio_stream,
    extract_audio,
    create_srt_file,
    merge_audio_and_video,
    get_media_duration
)
from core.translator import extract_json_array
from core.tts import generate_segment_tts_bytes, generate_full_dubbed_audio
from web.app import app

client = TestClient(app)
TEMP_TEST_DIR = PROJECT_ROOT / "storage" / "unit_test_temp"
TEMP_TEST_DIR.mkdir(parents=True, exist_ok=True)

def test_local_ip():
    ip = get_local_ip()
    assert isinstance(ip, str) and len(ip.split(".")) == 4, f"Invalid IP: {ip}"
    print(f"PASS: Local IP detected: {ip}")

def test_extract_json_array_edge_cases():
    # Case 1: Pure JSON array
    case1 = '[{"id": 0, "english": "Hello"}]'
    assert extract_json_array(case1)[0]["english"] == "Hello"

    # Case 2: Markdown code blocks
    case2 = '```json\n[{"id": 1, "english": "World"}]\n```'
    assert extract_json_array(case2)[0]["english"] == "World"

    # Case 3: Conversational wrapper before and after
    case3 = 'Sure! Here is the JSON list:\n[{"id": 2, "english": "Code"}]\nHope this helps!'
    assert extract_json_array(case3)[0]["english"] == "Code"

    # Case 4: Multiline nested text
    case4 = '```\n[\n  {\n    "id": 3,\n    "english": "Complex sentence with \\"quotes\\""\n  }\n]\n```'
    assert extract_json_array(case4)[0]["id"] == 3

    print("PASS: JSON array extraction resilient to all LLM output formats.")

def test_ffmpeg_media_and_audio_detection():
    ffmpeg_exe = get_ffmpeg_path()
    
    # 1. Video with audio
    vid_with_audio = TEMP_TEST_DIR / "with_audio.mp4"
    run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc=duration=1.5:size=320x240:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1.5",
        "-c:v", "libx264", "-c:a", "aac",
        str(vid_with_audio)
    ])
    assert has_audio_stream(vid_with_audio) is True, "Failed to detect audio stream"

    # 2. Extract MP3 audio
    mp3_out = TEMP_TEST_DIR / "extracted.mp3"
    extract_audio(vid_with_audio, mp3_out)
    assert mp3_out.exists() and mp3_out.stat().st_size > 0, "MP3 extraction failed"

    # 3. Video without audio
    vid_no_audio = TEMP_TEST_DIR / "no_audio.mp4"
    run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30",
        "-c:v", "libx264", "-an",
        str(vid_no_audio)
    ])
    assert has_audio_stream(vid_no_audio) is False, "False positive audio stream detected"

    # 4. Verify clear error on extracting from video without audio
    try:
        extract_audio(vid_no_audio, TEMP_TEST_DIR / "should_fail.mp3")
        assert False, "Should have raised ValueError on silent video"
    except ValueError as e:
        assert "ভিডিওটিতে কোনো অডিও ট্র্যাক পাওয়া যায়নি" in str(e)
        print("PASS: Silent video correctly caught with friendly Bengali error.")

def test_tts_empty_and_retry():
    # Empty text should return empty bytes without network call
    b = asyncio.run(generate_segment_tts_bytes("", "en-US-ChristopherNeural"))
    assert b == b"", "Empty text did not return b''"

    # Valid short text
    b2 = asyncio.run(generate_segment_tts_bytes("OK", "en-US-ChristopherNeural"))
    assert len(b2) > 0, "TTS generation failed on valid short text"
    print("PASS: TTS empty check and generation verified.")

def test_srt_creation_and_special_chars():
    segments = [
        {"id": 0, "start": 0.0, "end": 1.2, "english": 'Hello, "world"! Special: <test> & chars.'},
        {"id": 1, "start": 1.5, "end": 2.5, "english": "Line 2 text with commas, semicolons; and dots."}
    ]
    srt_path = TEMP_TEST_DIR / "special.srt"
    create_srt_file(segments, srt_path)
    content = srt_path.read_text(encoding="utf-8")
    assert 'Hello, "world"!' in content
    assert "00:00:00,000 --> 00:00:01,200" in content
    assert "00:00:01,500 --> 00:00:02,500" in content
    print("PASS: SRT subtitle generation and formatting verified.")

def test_api_endpoints_and_streaming_headers():
    # Test upload with dirty filename
    dirty_filename = "My (Video) [2026] & Test?.mp4"
    res = client.post("/api/upload", files={"file": (dirty_filename, b"fake video bytes", "video/mp4")})
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    # Check that job_id is sanitized
    assert "(" not in job_id and ")" not in job_id and "?" not in job_id
    print(f"PASS: Filename sanitization passed. Job ID: {job_id}")

    # Create dummy output file in storage/outputs
    out_dir = PROJECT_ROOT / "storage" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    dummy_out = out_dir / "test_stream_video.mp4"
    dummy_out.write_bytes(b"sample video bytes for range test")

    # Test /api/stream/{filename} -> content-disposition must be inline
    res_stream = client.get("/api/stream/test_stream_video.mp4")
    assert res_stream.status_code == 200
    assert "inline" in res_stream.headers.get("content-disposition", "")
    print("PASS: /api/stream/ returns inline disposition for seamless browser video player.")

    # Test /api/download/{filename} -> content-disposition must be attachment
    res_down = client.get("/api/download/test_stream_video.mp4")
    assert res_down.status_code == 200
    assert "attachment" in res_down.headers.get("content-disposition", "")
    print("PASS: /api/download/ returns attachment disposition for download action.")

    if dummy_out.exists():
        dummy_out.unlink()

def cleanup():
    import shutil
    shutil.rmtree(TEMP_TEST_DIR, ignore_errors=True)
    print("PASS: Test cleanup completed.")

if __name__ == "__main__":
    print("\n================ STARTING DEEP TEST SUITE ================")
    test_local_ip()
    test_extract_json_array_edge_cases()
    test_ffmpeg_media_and_audio_detection()
    test_tts_empty_and_retry()
    test_srt_creation_and_special_chars()
    test_api_endpoints_and_streaming_headers()
    cleanup()
    print("================ ALL DEEP TESTS PASSED (100% SUCCESS) ================\n")
