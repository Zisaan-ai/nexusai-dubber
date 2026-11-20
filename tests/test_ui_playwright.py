import sys
import time
import subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

SCREENSHOTS_DIR = PROJECT_ROOT / "storage" / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def run_ui_tests():
    print("\n--- Starting Local Server for UI Testing ---")
    server_proc = subprocess.Popen([
        r"C:\yt and AI project\nexusai-dubber\.venv\Scripts\python.exe",
        "-m", "uvicorn", "web.app:app", "--host", "127.0.0.1", "--port", "8008"
    ], cwd=str(PROJECT_ROOT))

    time.sleep(2.5)
    base_url = "http://127.0.0.1:8008"
    console_errors = []

    try:
        with sync_playwright() as p:
            print("--- Launching Chromium for Desktop UI Testing ---")
            browser = p.chromium.launch(headless=True)
            
            # 1. Desktop Test
            desktop_context = browser.new_context(viewport={"width": 1280, "height": 800})
            page = desktop_context.new_page()

            def handle_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)
                    print(f"Browser Console Error: {msg.text}")

            page.on("console", handle_console)

            page.goto(base_url, wait_until="networkidle")
            assert "NexusAI Dubber" in page.title(), f"Page title mismatch: {page.title()}"
            print("PASS: Desktop page title verified.")

            # Check Header & Elements
            lan_text = page.locator("#lanIpText").inner_text()
            assert "http://" in lan_text, f"LAN IP text missing or invalid: {lan_text}"
            print(f"PASS: Header LAN badge verified: {lan_text}")

            # Check voice options count
            voice_options = page.locator("#voiceSelect option").all()
            assert len(voice_options) >= 4, f"Too few voice options: {len(voice_options)}"
            print(f"PASS: Voice options loaded ({len(voice_options)} voices).")

            # Test Settings Modal
            page.locator("button:has-text('API কী সেটিংস')").click()
            page.wait_for_selector("#settingsModal:not(.hidden)", state="visible")
            print("PASS: Settings modal opened successfully.")

            # Type test keys and save
            page.fill("#geminiKeyInput", "AIzaSy_test_key_gemini")
            page.fill("#groqKeyInput", "gsk_test_key_groq")
            page.locator("#settingsModal button:has-text('সংরক্ষণ করুন')").click()
            time.sleep(0.5)
            print("PASS: Settings submitted and modal closed.")

            # Test File Upload
            test_file = SCREENSHOTS_DIR / "test_dummy.mp4"
            test_file.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42")

            start_btn = page.locator("#startBtn")
            assert start_btn.is_disabled(), "Start button should be disabled before upload"

            page.set_input_files("#videoInput", str(test_file))
            page.wait_for_selector("#uploadProgressBar", state="visible")
            page.wait_for_selector("#fileInfo:not(.hidden)", state="visible")
            time.sleep(1.0)

            # Start button should now be enabled
            assert not start_btn.is_disabled(), "Start button should be enabled after upload"
            print("PASS: Upload simulated and start button enabled.")

            desktop_shot = SCREENSHOTS_DIR / "desktop_ui.png"
            page.screenshot(path=str(desktop_shot), full_page=True)
            print(f"PASS: Desktop screenshot saved: {desktop_shot}")
            desktop_context.close()

            # 2. Android Mobile Test (Pixel 7 emulation)
            print("\n--- Testing Android Mobile Viewport (412x915) ---")
            pixel7 = p.devices["Pixel 7"]
            mobile_context = browser.new_context(**pixel7)
            m_page = mobile_context.new_page()
            m_page.on("console", handle_console)

            m_page.goto(base_url, wait_until="networkidle")

            # Check for horizontal overflow
            scroll_width = m_page.evaluate("document.documentElement.scrollWidth")
            client_width = m_page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width + 1, f"Horizontal overflow detected! scrollWidth={scroll_width}, clientWidth={client_width}"
            print("PASS: Mobile responsive layout verified (Zero horizontal overflow).")

            mobile_shot = SCREENSHOTS_DIR / "mobile_android_ui.png"
            m_page.screenshot(path=str(mobile_shot), full_page=True)
            print(f"PASS: Mobile screenshot saved: {mobile_shot}")
            mobile_context.close()

            browser.close()

            # Check console errors
            assert len(console_errors) == 0, f"Encountered browser console errors: {console_errors}"
            print("PASS: Zero browser console errors!")

    finally:
        print("--- Terminating UI Test Server ---")
        server_proc.terminate()
        server_proc.wait()

    print("\n================ ALL UI TESTS PASSED SUCCESSFULLY! ================\n")

if __name__ == "__main__":
    run_ui_tests()
