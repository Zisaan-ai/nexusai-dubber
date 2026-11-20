import asyncio
import io
import wave
import numpy as np
from pathlib import Path
from typing import List, Dict, Any
import edge_tts
from core.ffmpeg_utils import run_ffmpeg, get_ffmpeg_path
from config import Settings

SAMPLE_RATE = 24000

async def generate_segment_tts_bytes(text: str, voice: str, retries: int = 3) -> bytes:
    clean_text = text.strip()
    if not clean_text:
        return b""

    for attempt in range(1, retries + 1):
        try:
            communicate = edge_tts.Communicate(clean_text, voice)
            audio_data = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data.extend(chunk["data"])
            if audio_data:
                return bytes(audio_data)
        except Exception as e:
            if attempt == retries:
                print(f"Edge-TTS failed after {retries} attempts for '{clean_text}': {e}")
                raise
            await asyncio.sleep(0.5 * attempt)
    return b""

def convert_audio_to_pcm16_samples(input_bytes: bytes, target_sr: int = SAMPLE_RATE) -> np.ndarray:
    ffmpeg_exe = get_ffmpeg_path()
    import subprocess
    cmd = [
        ffmpeg_exe, "-y",
        "-i", "pipe:0",
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "-ac", "1",
        "-ar", str(target_sr),
        "pipe:1"
    ]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = p.communicate(input=input_bytes)
    if p.returncode != 0:
        raise RuntimeError(f"FFmpeg PCM conversion failed: {stderr.decode('utf-8', errors='ignore')}")
    
    samples = np.frombuffer(stdout, dtype=np.int16)
    return samples

async def generate_full_dubbed_audio(
    segments: List[Dict[str, Any]],
    total_duration: float,
    output_wav_path: Path,
    voice: str = None
) -> Path:
    if not voice:
        voice = Settings.get_default_voice()

    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    total_samples = int(np.ceil(total_duration * SAMPLE_RATE)) + SAMPLE_RATE
    master_buffer = np.zeros(total_samples, dtype=np.int16)

    for i, seg in enumerate(segments):
        eng_text = seg.get("english", "").strip()
        if not eng_text:
            continue

        start_sec = seg["start"]
        end_sec = seg["end"]
        allocated_dur = max(0.5, end_sec - start_sec)

        try:
            tts_bytes = await generate_segment_tts_bytes(eng_text, voice)
            seg_samples = convert_audio_to_pcm16_samples(tts_bytes, target_sr=SAMPLE_RATE)
            seg_dur = len(seg_samples) / SAMPLE_RATE

            # Micro-adjust speed if needed to fit window
            if seg_dur > allocated_dur * 1.1:
                # If too long, speed up by resampling
                target_len = int(allocated_dur * SAMPLE_RATE)
                indices = np.linspace(0, len(seg_samples) - 1, target_len).astype(int)
                seg_samples = seg_samples[indices]

            start_idx = int(start_sec * SAMPLE_RATE)
            end_idx = start_idx + len(seg_samples)

            if end_idx > len(master_buffer):
                # Expand buffer if video duration ran slightly past
                pad_len = end_idx - len(master_buffer)
                master_buffer = np.pad(master_buffer, (0, pad_len))

            # Mix samples with slight fade in/out to avoid clicks
            if len(seg_samples) > 200:
                fade_len = 100
                fade_in = np.linspace(0, 1, fade_len)
                fade_out = np.linspace(1, 0, fade_len)
                seg_samples[:fade_len] = (seg_samples[:fade_len] * fade_in).astype(np.int16)
                seg_samples[-fade_len:] = (seg_samples[-fade_len:] * fade_out).astype(np.int16)

            master_buffer[start_idx:end_idx] = seg_samples

        except Exception as e:
            print(f"Warning: TTS failed for segment {i} ('{eng_text}'): {e}")

    # Write WAV file
    with wave.open(str(output_wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(master_buffer.tobytes())

    return output_wav_path
