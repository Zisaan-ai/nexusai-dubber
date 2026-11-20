import sys
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def capture_studio():
    server_proc = subprocess.Popen([
        r"C:\yt and AI project\nexusai-dubber\.venv\Scripts\python.exe",
        "-m", "uvicorn", "web.app:app", "--host", "127.0.0.1", "--port", "8010"
    ], cwd=str(PROJECT_ROOT))

    time.sleep(2.5)
    base_url = "http://127.0.0.1:8010"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            
            # Desktop Studio
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(base_url, wait_until="networkidle")

            # Reveal the result card with sample state so we can see the full studio
            page.evaluate("""() => {
                document.getElementById('resultCard').classList.remove('hidden');
                renderSegments([
                    {id: 0, start: 0.0, end: 2.5, bengali: "সবাইকে স্বাগতম আমাদের নতুন ভিডিওতে", english: "Welcome everyone to our new video."},
                    {id: 1, start: 2.8, end: 5.2, bengali: "আজকে আমরা কোডিং করে এআই অ্যাপ বানাব", english: "Today we will code and build an AI app."},
                    {id: 2, start: 5.5, end: 8.0, bengali: "পুরো ভিডিওটি শেষ পর্যন্ত মনোযোগ দিয়ে দেখুন", english: "Please watch the entire video till the end."}
                ]);
                appendChatMessage('user', 'ভাই ৩ নম্বর লাইনের অনুবাদটা আরেকটু ক্যাজুয়াল আমেরিকান করো');
                appendChatMessage('assistant', 'আপনার নির্দেশ অনুযায়ী ৩ নম্বর লাইনের অনুবাদ আপডেট করা হয়েছে এবং অডিও রি-রেন্ডার সম্পন্ন হয়েছে!', 'লাইন #২ আপডেট সম্পন্ন');
            }""")

            time.sleep(1)
            shot_path = PROJECT_ROOT / "storage" / "screenshots" / "copilot_studio_live.png"
            page.screenshot(path=str(shot_path), full_page=True)
            print(f"Captured: {shot_path}")
            browser.close()
    finally:
        server_proc.terminate()
        server_proc.wait()

if __name__ == "__main__":
    capture_studio()
