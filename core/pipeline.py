import asyncio
from pathlib import Path
from typing import Dict, Any, Callable, Optional
from core.ffmpeg_utils import extract_audio, get_media_duration, create_srt_file, merge_audio_and_video
from core.stt import transcribe_audio
from core.translator import translate_segments
from core.tts import generate_full_dubbed_audio
from config import TEMP_DIR, OUTPUT_DIR

async def run_dubbing_pipeline(
    video_path: Path,
    voice: Optional[str] = None,
    burn_subtitles: bool = True,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    def update(stage: str, percent: int, msg: str, data: Any = None):
        if progress_callback:
            progress_callback({
                "stage": stage,
                "progress": percent,
                "message": msg,
                "data": data
            })

    job_id = video_path.stem
    temp_dir = TEMP_DIR / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)

    extracted_audio = temp_dir / "extracted_audio.mp3"
    dubbed_audio = temp_dir / "dubbed_master.wav"
    srt_path = temp_dir / "subtitles.srt"
    output_video = OUTPUT_DIR / f"{job_id}_english_dubbed.mp4"

    # Step 1: Probe video
    update("probe", 10, "ভিডিও ফাইল বিশ্লেষণ ও তথ্য নেওয়া হচ্ছে...")
    duration = get_media_duration(video_path)
    if duration <= 0:
        raise ValueError("ভিডিওর দৈর্ঘ্য নির্ণয় করা যায়নি। ফাইলটি সঠিক কি না যাচাই করুন।")

    # Step 2: Extract audio
    update("extract", 20, "ভিডিও থেকে মূল অডিও আলাদা করা হচ্ছে...")
    extract_audio(video_path, extracted_audio)

    # Step 3: Speech to Text
    update("stt", 40, "বাংলা অডিও শুনে নির্ভুল টাইমস্ট্যাম্প তৈরি হচ্ছে (Groq Whisper)...")
    loop = asyncio.get_running_loop()
    segments = await loop.run_in_executor(None, transcribe_audio, extracted_audio)
    if not segments:
        raise ValueError("ভিডিওতে কোনো কথ্য বাংলা ভাষা পাওয়া যায়নি।")

    # Step 4: Translate with Gemini
    update("translate", 60, "স্বাভাবিক আমেরিকান ইংরেজিতে অনুবাদ ও স্পিড সিঙ্ক করা হচ্ছে (Gemini)...")
    translated_segments = await loop.run_in_executor(None, translate_segments, segments)

    # Step 5: Text to Speech
    update("tts", 80, "প্রিমিয়াম নিউরাল ভয়েস তৈরি ও টাইমস্ট্যাম্প অনুযায়ী পিন করা হচ্ছে (Edge-TTS)...")
    await generate_full_dubbed_audio(
        segments=translated_segments,
        total_duration=duration,
        output_wav_path=dubbed_audio,
        voice=voice
    )

    # Step 6: Create Subtitles
    create_srt_file(translated_segments, srt_path)

    # Step 7: Merge Final Video
    update("render", 90, "নতুন অডিও এবং সাবটাইটেল দিয়ে চূড়ান্ত ভিডিও রেন্ডার করা হচ্ছে...")
    await loop.run_in_executor(
        None,
        merge_audio_and_video,
        video_path,
        dubbed_audio,
        output_video,
        srt_path,
        burn_subtitles
    )

    update("done", 100, "অভিনন্দন! আপনার ভিডিও সফলভাবে ইংরেজিতে ডাব করা হয়েছে।", {
        "output_filename": output_video.name,
        "duration": round(duration, 1),
        "segments_count": len(translated_segments)
    })

    return {
        "output_path": output_video,
        "srt_path": srt_path,
        "segments": translated_segments,
        "duration": duration
    }
