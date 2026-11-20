import os
import re
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import imageio_ffmpeg
    DEFAULT_FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    DEFAULT_FFMPEG = shutil.which("ffmpeg") or "ffmpeg"

def get_ffmpeg_path() -> str:
    if os.path.exists(DEFAULT_FFMPEG):
        return DEFAULT_FFMPEG
    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path
    return DEFAULT_FFMPEG

def run_ffmpeg(args: list) -> subprocess.CompletedProcess:
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [ffmpeg_exe, "-y"] + args
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg command failed: {' '.join(cmd)}\nError: {res.stderr}")
    return res

def has_audio_stream(video_path: Path) -> bool:
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [ffmpeg_exe, "-i", str(video_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    return bool(re.search(r"Stream\s+#\d+:\d+.*:\s*Audio:", res.stderr, re.IGNORECASE))

def extract_audio(video_path: Path, output_audio_path: Path) -> Path:
    if not has_audio_stream(video_path):
        raise ValueError("ভিডিওটিতে কোনো অডিও ট্র্যাক পাওয়া যায়নি। রেকর্ডিং ফাইলে অডিও আছে কি না নিশ্চিত করুন।")
    output_audio_path.parent.mkdir(parents=True, exist_ok=True)
    if output_audio_path.suffix.lower() == ".mp3":
        args = [
            "-i", str(video_path),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "64k",
            "-ar", "16000",
            "-ac", "1",
            str(output_audio_path)
        ]
    else:
        args = [
            "-i", str(video_path),
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            str(output_audio_path)
        ]
    run_ffmpeg(args)
    return output_audio_path

def get_media_duration(file_path: Path) -> float:
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [ffmpeg_exe, "-i", str(file_path)]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if match:
        h, m, s = match.groups()
        return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0

def adjust_audio_speed(input_audio: Path, output_audio: Path, speed: float) -> Path:
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    clamped_speed = max(0.5, min(2.0, speed))
    args = [
        "-i", str(input_audio),
        "-filter:a", f"atempo={clamped_speed:.3f}",
        str(output_audio)
    ]
    run_ffmpeg(args)
    return output_audio

def create_srt_file(segments: list, srt_path: Path) -> Path:
    def format_timestamp(seconds: float) -> str:
        ms = int(round((seconds % 1) * 1000))
        total_sec = int(seconds)
        s = total_sec % 60
        total_min = total_sec // 60
        m = total_min % 60
        h = total_min // 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_path.parent.mkdir(parents=True, exist_ok=True)
    with open(srt_path, "w", encoding="utf-8") as f:
        idx = 1
        for seg in segments:
            text = seg.get("english", "").strip()
            if not text:
                continue
            start_str = format_timestamp(seg.get("start", 0.0))
            end_str = format_timestamp(seg.get("end", 0.0))
            f.write(f"{idx}\n{start_str} --> {end_str}\n{text}\n\n")
            idx += 1
    return srt_path

def merge_audio_and_video(
    video_path: Path,
    dubbed_audio_path: Path,
    output_video_path: Path,
    srt_path: Optional[Path] = None,
    burn_subtitles: bool = False
) -> Path:
    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    
    if burn_subtitles and srt_path and srt_path.exists():
        escaped_srt = str(srt_path).replace("\\", "/").replace(":", "\\:")
        sub_filter = f"subtitles='{escaped_srt}':force_style='FontSize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Bold=1'"
        args = [
            "-i", str(video_path),
            "-i", str(dubbed_audio_path),
            "-filter_complex", f"[0:v]{sub_filter}[v]",
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "22",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_video_path)
        ]
    else:
        args = [
            "-i", str(video_path),
            "-i", str(dubbed_audio_path),
            "-c:v", "copy",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            str(output_video_path)
        ]
        
    run_ffmpeg(args)
    return output_video_path
