import os
import re
import time
import shutil
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import UPLOAD_DIR, OUTPUT_DIR, VOICES, Settings, get_local_ip
from core.pipeline import run_dubbing_pipeline
from core.copilot import process_copilot_command

app = FastAPI(title="NexusAI Dubber Studio")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JOBS: Dict[str, Dict[str, Any]] = {}

class SettingsPayload(BaseModel):
    gemini_key: Optional[str] = None
    groq_key: Optional[str] = None
    default_voice: Optional[str] = None

class ChatPayload(BaseModel):
    job_id: Optional[str] = None
    message: str

class SegmentEditPayload(BaseModel):
    job_id: str
    segment_id: int
    new_english: str

@app.get("/api/info")
def get_info():
    gemini_set = bool(Settings.get_gemini_api_key())
    groq_set = bool(Settings.get_groq_api_key())
    return {
        "local_ip": get_local_ip(),
        "port": int(os.getenv("PORT", 8000)),
        "voices": VOICES,
        "default_voice": Settings.get_default_voice(),
        "gemini_configured": gemini_set,
        "groq_configured": groq_set,
    }

@app.post("/api/settings")
def update_settings(payload: SettingsPayload):
    Settings.save_settings(
        gemini_key=payload.gemini_key,
        groq_key=payload.groq_key,
        default_voice=payload.default_voice
    )
    return {
        "status": "success",
        "message": "সেটিংস সফলভাবে সংরক্ষিত হয়েছে!",
        "gemini_configured": bool(Settings.get_gemini_api_key()),
        "groq_configured": bool(Settings.get_groq_api_key())
    }

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
        raise HTTPException(status_code=400, detail="অনুগ্রহ করে একটি সঠিক ভিডিও ফাইল (.mp4, .mov, .mkv) আপলোড করুন।")

    clean_name = re.sub(r"[^\w\-_]", "_", Path(file.filename).stem)
    unique_name = f"{clean_name}_{int(time.time() * 1000)}"
    dest_path = UPLOAD_DIR / f"{unique_name}{Path(file.filename).suffix.lower()}"

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    job_id = unique_name
    JOBS[job_id] = {
        "status": "uploaded",
        "progress": 0,
        "message": "ভিডিও আপলোড সম্পন্ন হয়েছে। ডাবিং শুরু করার জন্য প্রস্তুত।",
        "video_path": str(dest_path),
        "filename": file.filename
    }

    return {"job_id": job_id, "filename": file.filename}

async def execute_dubbing_task(job_id: str, video_path: Path, voice: str, burn_subtitles: bool):
    def on_progress(event: Dict[str, Any]):
        JOBS[job_id].update({
            "status": "processing",
            "stage": event.get("stage"),
            "progress": event.get("progress", 0),
            "message": event.get("message", ""),
            "data": event.get("data")
        })

    try:
        result = await run_dubbing_pipeline(
            video_path=video_path,
            voice=voice,
            burn_subtitles=burn_subtitles,
            progress_callback=on_progress
        )
        JOBS[job_id].update({
            "status": "completed",
            "progress": 100,
            "message": "ডাবিং সম্পন্ন হয়েছে!",
            "output_file": result["output_path"].name,
            "duration": result["duration"],
            "segments": result["segments"]
        })
    except Exception as e:
        JOBS[job_id].update({
            "status": "failed",
            "progress": 0,
            "message": f"ত্রুটি: {str(e)}"
        })

@app.post("/api/dub")
async def start_dubbing(
    job_id: str = Form(...),
    voice: Optional[str] = Form(None),
    burn_subtitles: bool = Form(True),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="জব পাওয়া যায়নি।")

    video_path = Path(JOBS[job_id]["video_path"])
    selected_voice = voice or Settings.get_default_voice()

    JOBS[job_id].update({
        "status": "queued",
        "progress": 5,
        "message": "ডাবিং টাস্ক শুরু হচ্ছে..."
    })

    background_tasks.add_task(
        execute_dubbing_task,
        job_id,
        video_path,
        selected_voice,
        burn_subtitles
    )

    return {"status": "started", "job_id": job_id}

@app.get("/api/jobs/{job_id}")
def get_job_status(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="জব পাওয়া যায়নি।")
    return JOBS[job_id]

@app.post("/api/chat")
async def chat_with_copilot(payload: ChatPayload):
    if payload.job_id:
        if payload.job_id not in JOBS:
            raise HTTPException(status_code=404, detail="জব পাওয়া যায়নি। প্রথমে একটি ভিডিও ডাবিং করুন।")
        job = JOBS[payload.job_id]
        if job.get("status") != "completed":
            raise HTTPException(status_code=400, detail="ভিডিও ডাবিং এখনও সম্পন্ন হয়নি। ডাবিং শেষ হলে এডিট করা যাবে।")
    else:
        job = {"voice": Settings.get_default_voice()}

    try:
        res = await process_copilot_command(payload.message, job)
        return {
            "status": "success",
            "reply": res["reply"],
            "action": res["action"],
            "action_details": res["action_details"],
            "output_file": res.get("updated_output_file"),
            "segments": res.get("segments", []),
            "voice": res.get("current_voice")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Copilot ত্রুটি: {str(e)}")

@app.get("/api/segments/{job_id}")
def get_job_segments(job_id: str):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="জব পাওয়া যায়নি।")
    return {
        "job_id": job_id,
        "segments": JOBS[job_id].get("segments", []),
        "output_file": JOBS[job_id].get("output_file")
    }

@app.get("/api/stream/{filename}")
def stream_output_video(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ফাইলটি পাওয়া যায়নি।")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="video/mp4",
        content_disposition_type="inline"
    )

@app.get("/api/download/{filename}")
def download_output_video(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="ফাইলটি পাওয়া যায়নি।")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="video/mp4",
        content_disposition_type="attachment"
    )

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/manifest.json")
def get_manifest():
    manifest_file = STATIC_DIR / "manifest.json"
    return FileResponse(manifest_file, media_type="application/manifest+json")

@app.get("/sw.js")
def get_service_worker():
    sw_file = STATIC_DIR / "sw.js"
    return FileResponse(sw_file, media_type="application/javascript")

TEMPLATES_DIR = Path(__file__).parent / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
def index_page():
    index_file = TEMPLATES_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>NexusAI Dubber Studio</h1>"
