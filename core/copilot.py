import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from google import genai
from groq import Groq
from config import Settings, VOICES, OUTPUT_DIR, TEMP_DIR
from core.ffmpeg_utils import create_srt_file, merge_audio_and_video, get_media_duration, run_ffmpeg
from core.tts import generate_full_dubbed_audio

AVAILABLE_VOICES = [v["id"] for v in VOICES]

SYSTEM_PROMPT_WITH_JOB = """
You are the NexusAI Studio Video Copilot — an expert AI Video Editor and Assistant.
The user has completed dubbing a video and will give you instructions in natural Bengali or English to edit their project.

CRITICAL RULE:
You MUST follow the user's instructions EXACTLY as requested ("ami jeta boli oita e korba").
Execute the exact edit or change they ask for.

Available Actions:
1. "edit_translation":
   Use when the user wants to change, rewrite, or polish the English translation of a specific sentence or line.
   Parameters:
     - "segment_id": (integer) ID of the segment to change (e.g. 0, 1, 2).
     - "new_english": (string) The exact new English text.

2. "change_voice":
   Use when the user wants to change the voice (e.g. to female, male, British, American).
   Parameters:
     - "voice": (string) One of:
       "en-US-ChristopherNeural" (Male US Energetic)
       "en-US-GuyNeural" (Male US Tech)
       "en-US-JennyNeural" (Female US Professional)
       "en-US-AriaNeural" (Female US Expressive)
       "en-GB-RyanNeural" (Male UK Tech)
       "en-GB-SoniaNeural" (Female UK British)

3. "change_subtitles":
   Use when user wants to change subtitle color, size, or toggle burning onto video.
   Parameters:
     - "font_size": (integer, e.g. 16, 20, 24)
     - "font_color": (string: "white", "yellow", "cyan")
     - "burn": (boolean, default true)

4. "trim_video":
   Use when user wants to cut or trim a time range from the video.
   Parameters:
     - "start_trim": (float, seconds from beginning to cut out, or start of cut)
     - "end_trim": (float, seconds to end of cut)

5. "chat_response":
   Use when the user is asking a question or greeting, and no file edit is required.
   Parameters:
     - "message": (string) Your response in polite, helpful Bengali.

Output Format:
You MUST return ONLY a valid JSON object with the following schema:
{
  "action": "edit_translation" | "change_voice" | "change_subtitles" | "trim_video" | "chat_response",
  "parameters": { ... },
  "reply_to_user": "আপনার নির্দেশ অনুযায়ী এডিট সম্পন্ন করা হয়েছে।"
}
Do not include any explanation or markdown formatting outside the JSON.
"""

SYSTEM_PROMPT_GENERAL = """
You are the NexusAI Studio Video Copilot — an expert AI Video Assistant.
The user is in the studio and may ask questions, ask to select a voice, ask how the app works, or ask to start dubbing.
There is currently no video dubbed yet.

Available Actions:
1. "change_voice":
   Use when the user asks to select or set a voice (e.g. "Jenny ভয়েস দাও", "মেয়ে কণ্ঠ সিলেক্ট করো", "Ryan সিলেক্ট করো").
   Parameters:
     - "voice": (string) The voice name (e.g. "en-US-JennyNeural", "en-US-ChristopherNeural", "en-GB-RyanNeural", etc.)
2. "start_dubbing":
   Use when the user says "ডাবিং শুরু করো", "ভিডিও ডাব করো", "start dubbing".
   Parameters: {}
3. "chat_response":
   Use for greetings, questions about how the app works, best voice recommendations, or general helpful chat.
   Parameters:
     - "message": (string) Your response in polite, helpful, and natural Bengali.

Output Format:
You MUST return ONLY a valid JSON object with the following schema:
{
  "action": "change_voice" | "start_dubbing" | "chat_response",
  "parameters": { ... },
  "reply_to_user": "আপনার উত্তর বা বার্তা এখানে লিখুন।"
}
Do not include any explanation or markdown formatting outside the JSON.
"""

def extract_json_object(text: str) -> dict:
    clean = text.strip()
    match = re.search(r"\{\s*\".*\"\s*:\s*.*\}", clean, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(clean[start:end+1])
    return json.loads(clean)

def resolve_voice_name(voice_input: str) -> str:
    v = (voice_input or "").lower()
    if "jenny" in v or "মেয়ে" in v or "female" in v or "নারী" in v or "woman" in v:
        return "en-US-JennyNeural"
    if "aria" in v:
        return "en-US-AriaNeural"
    if "guy" in v:
        return "en-US-GuyNeural"
    if "ryan" in v or "british" in v or "uk" in v:
        return "en-GB-RyanNeural"
    if "sonia" in v:
        return "en-GB-SoniaNeural"
    if "christopher" in v or "male" in v or "পুরুষ" in v or "boy" in v:
        return "en-US-ChristopherNeural"
    for av in AVAILABLE_VOICES:
        if av.lower() == v:
            return av
    return "en-US-ChristopherNeural"

def parse_segment_id(seg_raw: Any) -> Optional[int]:
    if isinstance(seg_raw, int):
        return seg_raw
    if seg_raw is None:
        return None
    match = re.search(r"\d+", str(seg_raw))
    return int(match.group(0)) if match else None

async def process_copilot_command(
    user_message: str,
    job_data: Dict[str, Any]
) -> Dict[str, Any]:
    gemini_key = Settings.get_gemini_api_key()
    groq_key = Settings.get_groq_api_key()

    if not gemini_key and not groq_key:
        return {
            "reply": "⚠️ ক্ষমা করবেন, কথা বলা বা এডিট করার জন্য আপনার Gemini API Key বা Groq Key প্রয়োজন। দয়া করে উপরের '⚙️ API কী সেটিংস' থেকে কী সেট করুন।",
            "action": "error",
            "action_details": "API Key অনুপস্থিত",
            "updated_output_file": job_data.get("output_file"),
            "segments": job_data.get("segments", []),
            "current_voice": job_data.get("voice")
        }

    segments = job_data.get("segments", [])
    current_voice = job_data.get("voice", Settings.get_default_voice())
    video_path_str = job_data.get("video_path", "")
    video_path = Path(video_path_str) if video_path_str else None
    duration = job_data.get("duration", 0.0)
    has_active_video = bool(job_data.get("status") == "completed" and video_path and video_path.exists())

    system_prompt = SYSTEM_PROMPT_WITH_JOB if has_active_video else SYSTEM_PROMPT_GENERAL

    if has_active_video:
        context = {
            "current_voice": current_voice,
            "video_duration_seconds": round(duration, 1),
            "total_segments": len(segments),
            "segments": [
                {
                    "id": s["id"],
                    "start": s["start"],
                    "end": s["end"],
                    "bengali": s["bengali"],
                    "english": s["english"]
                }
                for s in segments
            ]
        }
        user_prompt = f"Current Video Project Context:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\nUser's instruction:\n\"{user_message}\""
    else:
        user_prompt = f"Available voices: {AVAILABLE_VOICES}\nCurrent selected voice: {current_voice}\n\nUser's message:\n\"{user_message}\""

    raw_response = None
    if gemini_key:
        try:
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"{system_prompt}\n\n{user_prompt}"
            )
            raw_response = resp.text
        except Exception as e:
            if not groq_key:
                raise RuntimeError(f"Gemini Copilot Error: {e}")

    if not raw_response and groq_key:
        client = Groq(api_key=groq_key)
        chat = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        raw_response = chat.choices[0].message.content

    parsed = extract_json_object(raw_response)
    action = parsed.get("action", "chat_response")
    params = parsed.get("parameters", {})
    reply = parsed.get("reply_to_user", "আপনার নির্দেশ অনুযায়ী কাজ সম্পন্ন করা হয়েছে।")
    action_details = "বার্তা প্রদান করা হয়েছে"

    # If no active video, handle general actions
    if not has_active_video:
        if action == "change_voice":
            raw_v = params.get("voice", "")
            resolved = resolve_voice_name(raw_v)
            job_data["voice"] = resolved
            return {
                "reply": reply or f"ভয়েস হিসেবে {resolved} নির্ধারণ করা হয়েছে।",
                "action": "change_voice",
                "action_details": f"ভয়েস '{resolved}' সিলেক্ট করা হয়েছে",
                "current_voice": resolved,
                "voice": resolved,
                "segments": []
            }
        elif action == "start_dubbing":
            return {
                "reply": reply or "ডাবিং শুরু করা হচ্ছে...",
                "action": "start_dubbing",
                "action_details": "ডাবিং ট্রিগার করা হয়েছে",
                "current_voice": current_voice,
                "segments": []
            }
        else:
            return {
                "reply": reply,
                "action": "chat_response",
                "action_details": "বার্তা প্রদান করা হয়েছে",
                "current_voice": current_voice,
                "segments": []
            }

    # If has active video, handle editing actions
    version = job_data.get("version", 1) + 1
    job_data["version"] = version

    job_id = video_path.stem
    temp_dir = TEMP_DIR / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    srt_path = temp_dir / "subtitles.srt"
    dubbed_audio = temp_dir / f"dubbed_master_v{version}.wav"
    output_video = OUTPUT_DIR / f"{job_id}_v{version}.mp4"

    if action == "edit_translation":
        seg_id = parse_segment_id(params.get("segment_id"))
        new_text = params.get("new_english", "").strip()
        if seg_id is not None and new_text:
            found = False
            for s in segments:
                if s["id"] == seg_id:
                    s["english"] = new_text
                    found = True
                    break

            if found:
                create_srt_file(segments, srt_path)
                await generate_full_dubbed_audio(
                    segments=segments,
                    total_duration=duration,
                    output_wav_path=dubbed_audio,
                    voice=current_voice
                )
                merge_audio_and_video(
                    video_path=video_path,
                    dubbed_audio_path=dubbed_audio,
                    output_video_path=output_video,
                    srt_path=srt_path,
                    burn_subtitles=True
                )
                job_data["segments"] = segments
                job_data["output_file"] = output_video.name
                action_details = f"লাইন #{seg_id}-এর অনুবাদ পরিবর্তন এবং অডিও আপডেট সম্পন্ন"

    elif action == "change_voice":
        raw_v = params.get("voice", "")
        resolved = resolve_voice_name(raw_v)
        current_voice = resolved
        job_data["voice"] = resolved

        await generate_full_dubbed_audio(
            segments=segments,
            total_duration=duration,
            output_wav_path=dubbed_audio,
            voice=current_voice
        )
        merge_audio_and_video(
            video_path=video_path,
            dubbed_audio_path=dubbed_audio,
            output_video_path=output_video,
            srt_path=srt_path,
            burn_subtitles=True
        )
        job_data["output_file"] = output_video.name
        action_details = f"কণ্ঠ পরিবর্তন করে '{resolved}' করা হয়েছে এবং নতুন অডিও যুক্ত হয়েছে"

    elif action == "change_subtitles":
        font_size = params.get("font_size", 18)
        font_color = str(params.get("font_color", "white")).lower()
        burn = params.get("burn", True)

        color_hex = "&H00FFFFFF"
        if "yellow" in font_color or "হলুদ" in font_color:
            color_hex = "&H0000FFFF"
        elif "cyan" in font_color or "blue" in font_color or "নীল" in font_color:
            color_hex = "&H00FFFF00"

        if burn and srt_path.exists():
            escaped_srt = str(srt_path).replace("\\", "/").replace(":", "\\:")
            sub_filter = f"subtitles='{escaped_srt}':force_style='FontSize={font_size},PrimaryColour={color_hex},OutlineColour=&H00000000,BorderStyle=3,Bold=1,MarginV=25'"
            last_audio = dubbed_audio if dubbed_audio.exists() else temp_dir / "dubbed_master.wav"
            args = [
                "-i", str(video_path),
                "-i", str(last_audio),
                "-filter_complex", f"[0:v]{sub_filter}[v]",
                "-map", "[v]",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "veryfast",
                "-crf", "22",
                "-c:a", "aac",
                "-b:a", "192k",
                "-shortest",
                str(output_video)
            ]
            run_ffmpeg(args)
            job_data["output_file"] = output_video.name
            action_details = f"সাবটাইটেল স্টাইল (ফন্ট সাইজ: {font_size}, কালার: {font_color}) আপডেট সম্পন্ন"

    elif action == "trim_video":
        s_trim = float(params.get("start_trim", 0.0))
        e_trim = float(params.get("end_trim", duration))
        if e_trim > s_trim:
            trimmed_dur = e_trim - s_trim
            trimmed_source = temp_dir / f"trimmed_source_v{version}.mp4"
            run_ffmpeg([
                "-ss", str(s_trim),
                "-to", str(e_trim),
                "-i", str(video_path),
                "-c", "copy",
                str(trimmed_source)
            ])
            new_segments = []
            for s in segments:
                if s["end"] > s_trim and s["start"] < e_trim:
                    new_start = max(0.0, s["start"] - s_trim)
                    new_end = min(trimmed_dur, s["end"] - s_trim)
                    if new_end > new_start:
                        new_segments.append({
                            "id": len(new_segments),
                            "start": round(new_start, 2),
                            "end": round(new_end, 2),
                            "bengali": s["bengali"],
                            "english": s["english"]
                        })

            create_srt_file(new_segments, srt_path)
            await generate_full_dubbed_audio(
                segments=new_segments,
                total_duration=trimmed_dur,
                output_wav_path=dubbed_audio,
                voice=current_voice
            )
            merge_audio_and_video(
                video_path=trimmed_source,
                dubbed_audio_path=dubbed_audio,
                output_video_path=output_video,
                srt_path=srt_path,
                burn_subtitles=True
            )
            job_data["segments"] = new_segments
            job_data["duration"] = trimmed_dur
            job_data["video_path"] = str(trimmed_source)
            job_data["output_file"] = output_video.name
            action_details = f"ভিডিও {s_trim:.1f}s থেকে {e_trim:.1f}s পর্যন্ত ট্রিম করা হয়েছে"

    return {
        "reply": reply,
        "action": action,
        "action_details": action_details,
        "updated_output_file": job_data.get("output_file"),
        "segments": job_data.get("segments", segments),
        "current_voice": current_voice
    }
