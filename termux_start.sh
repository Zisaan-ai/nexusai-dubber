#!/data/data/com.termux/files/usr/bin/bash

echo "=========================================="
echo "    🚀 NexusAI Dubber Studio (Android)    "
echo "=========================================="

# 1. Update pkg & install dependencies if not installed
if ! command -v ffmpeg &> /dev/null || ! command -v python &> /dev/null; then
    echo "[*] Installing Python & FFmpeg (First-time setup)..."
    pkg update -y
    pkg install -y python ffmpeg git
fi

# 2. Clone or update repository
PROJECT_DIR="$HOME/nexusai-dubber"
if [ ! -d "$PROJECT_DIR" ]; then
    echo "[*] Downloading NexusAI Dubber Studio..."
    git clone https://github.com/Zisaan-ai/nexusai-dubber.git "$PROJECT_DIR"
else
    echo "[*] Updating NexusAI Dubber Studio..."
    cd "$PROJECT_DIR" && git pull origin main
fi

cd "$PROJECT_DIR"

# 3. Install lightweight python dependencies
echo "[*] Checking Python packages..."
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" python-multipart google-genai groq edge-tts imageio-ffmpeg aiofiles requests python-dotenv numpy

# 4. Create alias for instant startup next time
grep -qxF "alias nexus='cd ~/nexusai-dubber && python -m uvicorn web.app:app --host 0.0.0.0 --port 8000'" ~/.bashrc || echo "alias nexus='cd ~/nexusai-dubber && python -m uvicorn web.app:app --host 0.0.0.0 --port 8000'" >> ~/.bashrc

# 5. Launch Studio
echo ""
echo "=========================================="
echo "  ✅ NexusAI Dubber Studio is starting!   "
echo "  🌐 URL: http://localhost:8000           "
echo "=========================================="
echo ""

# Try opening the browser automatically
termux-open-url http://localhost:8000 2>/dev/null || am start -a android.intent.action.VIEW -d http://localhost:8000 2>/dev/null &

# Start FastAPI server on port 8000
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000
