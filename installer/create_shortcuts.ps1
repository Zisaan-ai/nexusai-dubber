$projectDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$vbsLauncher = Join-Path $projectDir "launch_desktop_app.vbs"
$iconPath = Join-Path $projectDir "app_icon.ico"

$wshShell = New-Object -ComObject WScript.Shell
$desktopDir = [Environment]::GetFolderPath("Desktop")
$userProfile = [Environment]::GetFolderPath("UserProfile")
$oneDriveDesktop = Join-Path $userProfile "OneDrive\Desktop"

# Only target Desktop (upore), remove from Start Menu (niche)
$targetDirs = @()
if (Test-Path $oneDriveDesktop) {
    $targetDirs += $oneDriveDesktop
} elseif (Test-Path $desktopDir) {
    $targetDirs += $desktopDir
}

# Ensure Start Menu shortcut is removed if it previously existed
$programsDir = [Environment]::GetFolderPath("Programs")
$oldStartMenuLnk = Join-Path $programsDir "NexusAI Dubber Studio.lnk"
if (Test-Path $oldStartMenuLnk) {
    Remove-Item $oldStartMenuLnk -Force
}

foreach ($dir in $targetDirs) {
    if (Test-Path $dir) {
        $lnkPath = Join-Path $dir "NexusAI Dubber Studio.lnk"
        $shortcut = $wshShell.CreateShortcut($lnkPath)
        $shortcut.TargetPath = "wscript.exe"
        $shortcut.Arguments = "`"$vbsLauncher`""
        $shortcut.WorkingDirectory = "$projectDir"
        $shortcut.IconLocation = "$iconPath,0"
        $shortcut.Description = "NexusAI Dubber Studio — বাংলা ➔ প্রফেশনাল আমেরিকান ইংলিশ ডাবিং"
        $shortcut.Save()
        Write-Host "[OK] Desktop Shortcut created: $lnkPath" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  ইনস্টলেশন সফলভাবে সম্পন্ন হয়েছে!" -ForegroundColor Green
Write-Host "  শুধুমাত্র ডেস্কটপে (উপরে) আইকন রাখা হয়েছে, নিচে রাখা হয়নি।" -ForegroundColor Yellow
Write-Host "  এবং পিসি অন করলে বা উইন্ডোজে ঢুকলে কোনো অটো স্টার্ট হবে না।" -ForegroundColor Yellow
Write-Host "================================================================" -ForegroundColor Cyan
