import subprocess
import time
import urllib.request
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\higan\.gemini\antigravity\brain\2b71a4d3-257f-4da6-a1e4-4ef3b9271397")
EDGE_EXE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
PYTHON_EXE = r"C:\yt and AI project\nexusai-dubber\.venv\Scripts\python.exe"

def wait_for_server(url="http://127.0.0.1:8000/api/info", timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False

def main():
    # Check if server is already running
    server_proc = None
    if not wait_for_server(timeout=1):
        print("Starting uvicorn server...")
        server_proc = subprocess.Popen(
            [PYTHON_EXE, "-m", "uvicorn", "web.app:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=r"C:\yt and AI project\nexusai-dubber"
        )
        if not wait_for_server(timeout=10):
            print("Failed to start server")
            if server_proc:
                server_proc.kill()
            return

    print("Server is ready at http://127.0.0.1:8000")
    time.sleep(1)

    desktop_out = ARTIFACT_DIR / "desktop_studio_with_chatbot.png"
    mobile_out = ARTIFACT_DIR / "mobile_studio_with_chatbot.png"

    # Capture Desktop screenshot (1280x820)
    print(f"Capturing Desktop screenshot to {desktop_out}...")
    subprocess.run([
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        f"--screenshot={str(desktop_out)}",
        "--window-size=1280,820",
        "--virtual-time-budget=2000",
        "http://127.0.0.1:8000"
    ], check=True)

    # Capture Mobile screenshot (412x915)
    print(f"Capturing Mobile screenshot to {mobile_out}...")
    subprocess.run([
        EDGE_EXE,
        "--headless",
        "--disable-gpu",
        f"--screenshot={str(mobile_out)}",
        "--window-size=412,915",
        "--virtual-time-budget=2000",
        "http://127.0.0.1:8000"
    ], check=True)

    print("Desktop screenshot exists:", desktop_out.exists(), desktop_out.stat().st_size)
    print("Mobile screenshot exists:", mobile_out.exists(), mobile_out.stat().st_size)

    if server_proc:
        server_proc.terminate()

if __name__ == "__main__":
    main()
