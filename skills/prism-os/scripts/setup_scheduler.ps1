# PRISM-OS Phase 6 auto sync task installer
#
# Usage (PowerShell as Administrator):
#   powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
#
# Creates a Windows scheduled task that runs daily at 11:00.
# Task name: PRISM-OS Metrics Sync
# Log path: D:\myproject\PRISM-OSv1\logs\metrics_sync.log
#
# Note: Your computer must be powered on at the scheduled time.

$taskName = "PRISM-OS Metrics Sync"
$scriptPath = "D:\myproject\PRISM-OSv1\skills\prism-os\scripts\metrics_sync_wrapper.bat"
$logDir = "D:\myproject\PRISM-OSv1\logs"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$batContent = @"
@echo off
set LOGFILE=$logDir\metrics_sync.log
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set PYTHONPATH=D:\myproject\PRISM-OSv1\skills\prism-os\scripts
echo === %date% %time% start === >> %LOGFILE%
cd /d D:\myproject\PRISM-OSv1\skills\prism-os\scripts
python prism_os.py metrics sync >> %LOGFILE% 2>&1
echo === sync done === >> %LOGFILE%
python prism_os.py metrics score >> %LOGFILE% 2>&1
echo === score done === >> %LOGFILE%
echo. >> %LOGFILE%
"@

Set-Content -Path $scriptPath -Value $batContent -Encoding ASCII
Write-Host "[OK] Wrapper script created: $scriptPath"

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "[OK] Old task removed: $taskName"
}

$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -Daily -At "11:00"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "PRISM-OS Phase 6 auto sync: runs daily at 11:00" | Out-Null

Write-Host ""
Write-Host "[OK] Scheduled task created: $taskName"
Write-Host "  Schedule: Daily at 11:00 (when your PC is typically on)"
Write-Host "  Log: $logDir\metrics_sync.log"
Write-Host ""
Write-Host "  View task: Get-ScheduledTask -TaskName '$taskName'"
Write-Host "  Run now: Start-ScheduledTask -TaskName '$taskName'"
Write-Host "  Remove: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
Write-Host ""
Write-Host "  Note: PC must be powered on. If 11:00 PC is off, that day is skipped."
