import json
import re
from typing import List, Dict, Any
from google import genai
from groq import Groq
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

def translate_segments_with_gemini(segments: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    client = genai.Client(api_key=api_key)
    
    input_data = []
    for s in segments:
        duration = round(s["end"] - s["start"], 2)
        input_data.append({
            "id": s["id"],
            "start": s["start"],
            "end": s["end"],
            "duration": duration,
            "bengali": s["text"]
        })

    prompt = f"""
You are an expert YouTube tech tutorial dubbing translator.
Translate each Bengali sentence into punchy, natural, fluent American English suitable for a high-engagement YouTube or Shorts tutorial.

CRITICAL DURATION CONSTRAINT:
- For each segment, look at 'duration' (seconds).
- Average natural speaking rate is approx 2.5 words per second.
- The translated English sentence MUST fit naturally within that segment's duration without being too long or too short!
- Keep technical terms intact (e.g. Python, API, code, terminal, run, install, free, link).

Input segments:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

Return ONLY a valid JSON array of objects with the exact schema:
[
  {{
    "id": 0,
    "start": 0.0,
    "end": 2.5,
    "bengali": "...",
    "english": "..."
  }}
]
No additional prose or markdown code blocks.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    clean_text = response.text.strip()
    translated_list = extract_json_array(clean_text)
    
    # Merge back to assure structure
    result = []
    trans_map = {item["id"]: item.get("english", "") for item in translated_list}
    for seg in segments:
        eng = trans_map.get(seg["id"], "").strip()
        result.append({
            "id": seg["id"],
            "start": seg["start"],
            "end": seg["end"],
            "bengali": seg["text"],
            "english": eng or seg["text"]
        })
    return result

def translate_segments_with_groq(segments: List[Dict[str, Any]], api_key: str) -> List[Dict[str, Any]]:
    client = Groq(api_key=api_key)
    input_data = []
    for s in segments:
        duration = round(s["end"] - s["start"], 2)
        input_data.append({
            "id": s["id"],
            "duration": duration,
            "bengali": s["text"]
        })

    prompt = f"""
Translate each Bengali line into concise, natural American English fitting the specified 'duration' (2.5 words per sec).
Return ONLY JSON:
[
  {{"id": 0, "english": "..."}}
]

Segments:
{json.dumps(input_data, ensure_ascii=False)}
"""
    chat_completion = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama-3.3-70b-versatile",
        temperature=0.3,
        response_format={"type": "json_object"}
    )
    raw = chat_completion.choices[0].message.content
    data = json.loads(raw)
    items = data.get("segments", data if isinstance(data, list) else data.get("data", []))
    if isinstance(data, dict) and not isinstance(items, list):
        items = list(data.values())[0] if data else []

    trans_map = {}
    for it in items:
        if isinstance(it, dict) and "id" in it and "english" in it:
            trans_map[it["id"]] = it["english"]

    result = []
    for seg in segments:
        eng = trans_map.get(seg["id"], "").strip()
        result.append({
            "id": seg["id"],
            "start": seg["start"],
            "end": seg["end"],
            "bengali": seg["text"],
            "english": eng or seg["text"]
        })
    return result

def translate_segments(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    gemini_key = Settings.get_gemini_api_key()
    groq_key = Settings.get_groq_api_key()

    if gemini_key:
        try:
            return translate_segments_with_gemini(segments, gemini_key)
        except Exception as e:
            if not groq_key:
                raise RuntimeError(f"Gemini translation failed: {e}")

    if groq_key:
        return translate_segments_with_groq(segments, groq_key)

    raise ValueError("Neither GEMINI_API_KEY nor GROQ_API_KEY is configured for translation.")
