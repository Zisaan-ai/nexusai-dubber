$wshShell = New-Object -ComObject WScript.Shell
$desktopDir = [Environment]::GetFolderPath("Desktop")
$programsDir = [Environment]::GetFolderPath("Programs")
$userProfile = [Environment]::GetFolderPath("UserProfile")
$oneDriveDesktop = Join-Path $userProfile "OneDrive\Desktop"

$targetDirs = @($desktopDir, $programsDir, $oneDriveDesktop)

foreach ($dir in $targetDirs) {
    if (Test-Path $dir) {
        $lnkPath = Join-Path $dir "NexusAI Dubber Studio.lnk"
        if (Test-Path $lnkPath) {
            Remove-Item $lnkPath -Force
            Write-Host "[OK] Removed: $lnkPath" -ForegroundColor Green
        }
    }
}
Write-Host "আনইনস্টলেশন সম্পন্ন হয়েছে।" -ForegroundColor Green
