import os
import socket
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"
TEMP_DIR = BASE_DIR / "storage" / "temp"

for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    d.mkdir(parents=True, exist_ok=True)

VOICES = [
    {"id": "en-US-ChristopherNeural", "name": "Christopher (US - Energetic & Natural Male)", "gender": "Male"},
    {"id": "en-US-GuyNeural", "name": "Guy (US - Casual & Tech Male)", "gender": "Male"},
    {"id": "en-US-JennyNeural", "name": "Jenny (US - Professional Female)", "gender": "Female"},
    {"id": "en-US-AriaNeural", "name": "Aria (US - Expressive Female)", "gender": "Female"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (UK - British Tech Male)", "gender": "Male"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (UK - British Female)", "gender": "Female"},
]

def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class Settings:
    @staticmethod
    def get_gemini_api_key() -> str:
        return os.getenv("GEMINI_API_KEY", "")

    @staticmethod
    def get_groq_api_key() -> str:
        return os.getenv("GROQ_API_KEY", "")

    @staticmethod
    def get_default_voice() -> str:
        return os.getenv("DEFAULT_VOICE", "en-US-ChristopherNeural")

    @staticmethod
    def save_settings(gemini_key: str = None, groq_key: str = None, default_voice: str = None):
        current_env = {}
        if ENV_PATH.exists():
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        k, v = line.strip().split("=", 1)
                        current_env[k.strip()] = v.strip()

        if gemini_key is not None:
            current_env["GEMINI_API_KEY"] = gemini_key.strip()
            os.environ["GEMINI_API_KEY"] = gemini_key.strip()
        if groq_key is not None:
            current_env["GROQ_API_KEY"] = groq_key.strip()
            os.environ["GROQ_API_KEY"] = groq_key.strip()
        if default_voice is not None:
            current_env["DEFAULT_VOICE"] = default_voice.strip()
            os.environ["DEFAULT_VOICE"] = default_voice.strip()

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            for k, v in current_env.items():
                f.write(f"{k}={v}\n")
