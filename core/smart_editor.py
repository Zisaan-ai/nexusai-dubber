import subprocess
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
try:
    import cv2
except ImportError:
    cv2 = None
from core.ffmpeg_utils import get_ffmpeg_path

def detect_audio_silences(
    audio_path: Path,
    noise_db: float = -30.0,
    min_silence_sec: float = 1.0
) -> List[Dict[str, float]]:
    ffmpeg_exe = get_ffmpeg_path()
    cmd = [
        ffmpeg_exe, "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_sec}",
        "-f", "null", "-"
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore")
    
    silences = []
    current_start = None
    for line in res.stderr.splitlines():
        start_match = re.search(r"silence_start:\s*([\d\.]+)", line)
        if start_match:
            current_start = float(start_match.group(1))
        end_match = re.search(r"silence_end:\s*([\d\.]+)\s*\|\s*silence_duration:\s*([\d\.]+)", line)
        if end_match and current_start is not None:
            end_t = float(end_match.group(1))
            dur = float(end_match.group(2))
            if end_t > current_start and dur > 0:
                silences.append({
                    "start": round(current_start, 2),
                    "end": round(end_t, 2),
                    "duration": round(dur, 2)
                })
            current_start = None
            
    return silences

def check_visual_activity(video_path: Path, start_time: float, end_time: float, threshold_diff: float = 0.015) -> bool:
    if cv2 is None:
        return False
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False
        
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_start = int(start_time * fps)
    frame_mid = int(((start_time + end_time) / 2.0) * fps)
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_start)
    ret1, f1 = cap.read()
    
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_mid)
    ret2, f2 = cap.read()
    cap.release()
    
    if not (ret1 and ret2) or f1 is None or f2 is None:
        return False
        
    g1 = cv2.cvtColor(f1, cv2.COLOR_BGR2GRAY)
    g2 = cv2.cvtColor(f2, cv2.COLOR_BGR2GRAY)
    
    diff = cv2.absdiff(g1, g2)
    _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
    changed_pixels = cv2.countNonZero(thresh)
    total_pixels = g1.shape[0] * g1.shape[1]
    
    ratio = changed_pixels / max(1, total_pixels)
    return ratio > threshold_diff
