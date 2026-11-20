import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
VBS_LAUNCHER = PROJECT_DIR / "launch_desktop_app.vbs"
ICON_PATH = PROJECT_DIR / "app_icon.ico"

def install():
    import win32com.client
    wscript = win32com.client.Dispatch("WScript.Shell")

    desktop_dir = Path(wscript.SpecialFolders("Desktop"))
    programs_dir = Path(wscript.SpecialFolders("Programs"))

    for target_dir, label in [(desktop_dir, "Desktop"), (programs_dir, "Start Menu")]:
        lnk_path = target_dir / "NexusAI Dubber Studio.lnk"
        s = wscript.CreateShortcut(str(lnk_path))
        s.TargetPath = "wscript.exe"
        s.Arguments = f'"{str(VBS_LAUNCHER)}"'
        s.WorkingDirectory = str(PROJECT_DIR)
        s.IconLocation = f"{str(ICON_PATH)},0"
        s.Description = "NexusAI Dubber Studio — বাংলা ➔ প্রফেশনাল আমেরিকান ইংলিশ ডাবিং"
        s.Save()
        print(f"[OK] {label} shortcut created: {lnk_path.name}")

    print("\n🎉 ইনস্টলেশন সম্পন্ন হয়েছে!")
    print("এখন থেকে আপনি যেকোনো সাধারণ সফটওয়্যারের মতো আপনার ডেস্কটপ বা স্টার্ট মেনুর আইকনে ক্লিক করলেই অ্যাপ ওপেন হবে।")

def uninstall():
    import win32com.client
    wscript = win32com.client.Dispatch("WScript.Shell")
    desktop_dir = Path(wscript.SpecialFolders("Desktop"))
    programs_dir = Path(wscript.SpecialFolders("Programs"))

    for target_dir in [desktop_dir, programs_dir]:
        lnk = target_dir / "NexusAI Dubber Studio.lnk"
        if lnk.exists():
            lnk.unlink()
            print(f"[OK] Removed: {lnk}")
    print("আনইনস্টলেশন সম্পন্ন হয়েছে।")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall()
    else:
        install()
