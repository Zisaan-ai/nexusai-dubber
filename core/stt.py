import json
import re
from pathlib import Path
from typing import List, Dict, Any
from groq import Groq
from google import genai
from config import Settings

def extract_json_array(text: str) -> list:
    clean = text.strip()
    match = re.search(r"\[\s*\{.*\}\s*\]", clean, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    start = clean.find("[")
    end = clean.rfind("]")
    if start != -1 and end != -1 and end > start:
        return json.loads(clean[start:end+1])
    return json.loads(clean)

def transcribe_with_groq(audio_path: Path, api_key: str) -> List[Dict[str, Any]]:
    client = Groq(api_key=api_key)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            file=(audio_path.name, f.read()),
            model="whisper-large-v3",
            language="bn",
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    segments = []
    raw_segments = getattr(response, "segments", None)
    if not raw_segments and isinstance(response, dict):
        raw_segments = response.get("segments", [])

    if raw_segments:
        for idx, seg in enumerate(raw_segments):
            if isinstance(seg, dict):
                start = seg.get("start", 0.0)
                end = seg.get("end", 0.0)
                text = seg.get("text", "").strip()
            else:
                start = getattr(seg, "start", 0.0)
                end = getattr(seg, "end", 0.0)
                text = getattr(seg, "text", "").strip()

            if text:
                segments.append({
                    "id": idx,
                    "start": round(float(start), 2),
                    "end": round(float(end), 2),
                    "text": text
                })
    return segments

def transcribe_with_gemini(audio_path: Path, api_key: str) -> List[Dict[str, Any]]:
    client = genai.Client(api_key=api_key)
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    prompt = """
You are an expert audio transcriber. Listen carefully to this Bengali speech.
Transcribe it into sentence-level segments with precise timestamps (in seconds).
Return ONLY a valid JSON array of objects with the schema:
[
  {
    "id": 0,
    "start": 0.0,
    "end": 2.5,
    "text": "এখানে যা বলা হয়েছে..."
  }
]
Do not include any explanation or markdown formatting, just the raw JSON.
"""
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            genai.types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
            prompt
        ]
    )

    clean_text = response.text.strip()
    data = extract_json_array(clean_text)
    return data

def transcribe_audio(audio_path: Path) -> List[Dict[str, Any]]:
    groq_key = Settings.get_groq_api_key()
    gemini_key = Settings.get_gemini_api_key()

    if groq_key:
        try:
            return transcribe_with_groq(audio_path, groq_key)
        except Exception as e:
            if not gemini_key:
                raise RuntimeError(f"Groq transcription failed: {e}. Please check your Groq API Key.")

    if gemini_key:
        return transcribe_with_gemini(audio_path, gemini_key)

    raise ValueError("Neither GROQ_API_KEY nor GEMINI_API_KEY is configured. Please set at least one in Settings.")
