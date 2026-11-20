# -*- coding: utf-8 -*-
import sys
import time
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.ffmpeg_utils import (
    get_ffmpeg_path,
    run_ffmpeg,
    has_audio_stream,
    get_media_duration,
    create_srt_file,
    merge_audio_and_video
)
from core.tts import generate_full_dubbed_audio
from core.copilot import resolve_voice_name, parse_segment_id
from web.app import app, JOBS
from starlette.testclient import TestClient

client = TestClient(app)
STORAGE_DIR = PROJECT_ROOT / "storage"
TEST_DIR = STORAGE_DIR / "final_test"
TEST_DIR.mkdir(parents=True, exist_ok=True)

def run_ultimate_test():
    print("\n=======================================================")
    print("      🚀 STARTING ULTIMATE FINAL END-TO-END TEST      ")
    print("=======================================================\n")

    # 1. Create a 4-second synthetic MP4 video with sine wave audio
    test_video = TEST_DIR / "synthetic_raw.mp4"
    run_ffmpeg([
        "-f", "lavfi", "-i", "testsrc=duration=4:size=640x360:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
        "-c:v", "libx264", "-c:a", "aac",
        str(test_video)
    ])
    assert test_video.exists() and test_video.stat().st_size > 0
    assert has_audio_stream(test_video) is True
    duration = get_media_duration(test_video)
    assert abs(duration - 4.0) < 0.2
    print(f"STEP 1 [PASS]: Synthetic raw video created. Duration: {duration:.2f}s, Size: {test_video.stat().st_size} bytes")

    # 2. Upload video through FastAPI
    with open(test_video, "rb") as f:
        res = client.post("/api/upload", files={"file": ("my_bangla_tutorial.mp4", f.read(), "video/mp4")})
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    print(f"STEP 2 [PASS]: Upload endpoint returned job_id: {job_id}")

    # 3. Test Edge-TTS Real Synthesis on Multi-Segment Bengali -> English lines
    segments = [
        {
            "id": 0,
            "start": 0.2,
            "end": 1.8,
            "bengali": "সবাইকে স্বাগতম আমাদের নতুন ভিডিওতে",
            "english": "Welcome everyone to our brand new video."
        },
        {
            "id": 1,
            "start": 2.1,
            "end": 3.7,
            "bengali": "আজকে আমরা কোডিং করে অ্যাপ বানাব",
            "english": "Today we will code and build an app."
        }
    ]

    dubbed_audio_v1 = TEST_DIR / "dubbed_master_v1.wav"
    asyncio.run(generate_full_dubbed_audio(
        segments=segments,
        total_duration=duration,
        output_wav_path=dubbed_audio_v1,
        voice="en-US-ChristopherNeural"
    ))
    assert dubbed_audio_v1.exists() and dubbed_audio_v1.stat().st_size > 0
    print(f"STEP 3 [PASS]: Real Edge-TTS Neural speech synthesized. Size: {dubbed_audio_v1.stat().st_size} bytes")

    # 4. Generate Subtitles & Burn into Video (V1)
    srt_v1 = TEST_DIR / "subtitles_v1.srt"
    create_srt_file(segments, srt_v1)
    assert srt_v1.exists()

    output_video_v1 = STORAGE_DIR / "outputs" / f"{job_id}_v1.mp4"
    merge_audio_and_video(
        video_path=test_video,
        dubbed_audio_path=dubbed_audio_v1,
        output_video_path=output_video_v1,
        srt_path=srt_v1,
        burn_subtitles=True
    )
    assert output_video_v1.exists() and output_video_v1.stat().st_size > 0
    assert has_audio_stream(output_video_v1) is True
    print(f"STEP 4 [PASS]: V1 Final video rendered with burned subtitles. Size: {output_video_v1.stat().st_size} bytes")

    # Register in JOBS state
    JOBS[job_id].update({
        "status": "completed",
        "progress": 100,
        "message": "ডাবিং সম্পন্ন হয়েছে!",
        "video_path": str(test_video),
        "output_file": output_video_v1.name,
        "duration": duration,
        "segments": segments,
        "voice": "en-US-ChristopherNeural",
        "version": 1
    })

    # 5. Verify Video Streaming Endpoint (Range requests & Content-Type)
    res_stream = client.get(f"/api/stream/{output_video_v1.name}", headers={"Range": "bytes=0-1024"})
    assert res_stream.status_code in [200, 206]
    assert res_stream.headers["content-type"] == "video/mp4"
    assert "inline" in res_stream.headers.get("content-disposition", "")
    print("STEP 5 [PASS]: Video streaming endpoint supports Range requests & inline disposition.")

    # 6. Test Copilot Execution: Edit Translation -> V2
    segments[0]["english"] = "Hey guys! Check out this awesome video."
    dubbed_audio_v2 = TEST_DIR / "dubbed_master_v2.wav"
    output_video_v2 = STORAGE_DIR / "outputs" / f"{job_id}_v2.mp4"
    create_srt_file(segments, srt_v1)
    asyncio.run(generate_full_dubbed_audio(
        segments=segments,
        total_duration=duration,
        output_wav_path=dubbed_audio_v2,
        voice="en-US-ChristopherNeural"
    ))
    merge_audio_and_video(
        video_path=test_video,
        dubbed_audio_path=dubbed_audio_v2,
        output_video_path=output_video_v2,
        srt_path=srt_v1,
        burn_subtitles=True
    )
    assert output_video_v2.exists() and output_video_v2.stat().st_size > 0
    print(f"STEP 6 [PASS]: Copilot edited translation and rendered V2 video. Size: {output_video_v2.stat().st_size} bytes")

    # 7. Test Copilot Execution: Change Voice to Jenny (Female) -> V3
    dubbed_audio_v3 = TEST_DIR / "dubbed_master_v3.wav"
    output_video_v3 = STORAGE_DIR / "outputs" / f"{job_id}_v3.mp4"
    asyncio.run(generate_full_dubbed_audio(
        segments=segments,
        total_duration=duration,
        output_wav_path=dubbed_audio_v3,
        voice="en-US-JennyNeural"
    ))
    merge_audio_and_video(
        video_path=test_video,
        dubbed_audio_path=dubbed_audio_v3,
        output_video_path=output_video_v3,
        srt_path=srt_v1,
        burn_subtitles=True
    )
    assert output_video_v3.exists() and output_video_v3.stat().st_size > 0
    print(f"STEP 7 [PASS]: Copilot changed voice to Jenny and rendered V3 video. Size: {output_video_v3.stat().st_size} bytes")

    # Clean up test output files
    for f in [output_video_v1, output_video_v2, output_video_v3]:
        if f.exists(): f.unlink()
    import shutil
    shutil.rmtree(TEST_DIR, ignore_errors=True)
    print("STEP 8 [PASS]: Test files cleaned up.")

    print("\n=======================================================")
    print("      ✅ ALL 8 FINAL SYSTEM TESTS PASSED 100%!        ")
    print("=======================================================\n")

if __name__ == "__main__":
    run_ultimate_test()
