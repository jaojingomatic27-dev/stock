# ============================================================
# Windows Scheduled Task: daily rotation signal check
# ============================================================
# Usage (run as Administrator in PowerShell):
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1 -SendEmail
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1 -Mode status
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1 -Mode uninstall
# ============================================================

param(
    [string]$Mode = "install",
    [string]$Time = "04:30",
    [switch]$SendEmail = $false
)

$TaskName = "StockRotationSignal"
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "ERROR: Python not found in PATH." -ForegroundColor Red
    exit 1
}

$ScriptPath = Join-Path (Get-Location) "code\rotation_signal.py"
$EmailFlag = if ($SendEmail) { " --email" } else { "" }

# ============================================================
# STATUS
# ============================================================
if ($Mode -eq "status") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Scheduled Task Status" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "  Task:     $TaskName" -ForegroundColor Green
        Write-Host "  State:    $($task.State)" -ForegroundColor $(if($task.State -eq 'Ready'){'Green'}else{'Yellow'})
        Write-Host "  Trigger:  $($task.Triggers | ForEach-Object { $_.ToString() })"
        Write-Host "  Last Run: $($task.LastRunTime)"
        Write-Host "  Result:   $($task.LastTaskResult)"
    } else {
        Write-Host "  Task not installed." -ForegroundColor Yellow
        Write-Host "  Run: setup_scheduled_task.ps1" -ForegroundColor Gray
    }
    Write-Host ""
    exit 0
}

# ============================================================
# UNINSTALL
# ============================================================
if ($Mode -eq "uninstall") {
    Write-Host ""
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "  [OK] Removed: $TaskName" -ForegroundColor Green
    } else {
        Write-Host "  [!] Not found: $TaskName" -ForegroundColor Yellow
    }
    Write-Host ""
    exit 0
}

# ============================================================
# INSTALL
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Install Scheduled Task" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Python:   $PythonPath"
Write-Host "  Script:   $ScriptPath"
Write-Host "  Schedule: Daily at $Time (local time)"
Write-Host "  Email:    $(if($SendEmail){'Yes'}else{'No (terminal only)'})"
Write-Host ""

# Remove old task
$old = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "  Removing old task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create new task
$Action = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --check$EmailFlag" `
    -WorkingDirectory (Get-Location).Path

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun:$false `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30)

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

try {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "Daily check of Turbo warrant rotation signals" `
        -Force | Out-Null

    Write-Host "  [OK] Task installed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Task:     $TaskName"
    Write-Host "  Daily at: $Time (local time)"
    Write-Host "  Command:  python code\rotation_signal.py --check$EmailFlag"
    Write-Host "  Manage:   taskschd.msc -> search '$TaskName'"
    Write-Host "  Test:     python code\rotation_signal.py --check"
    Write-Host ""
    Write-Host "  Email setup (if not done):"
    Write-Host "    1. Copy .env.template -> .env"
    Write-Host "    2. Fill in Gmail app password"
    Write-Host "    3. Re-run: setup_scheduled_task.ps1 -SendEmail"
    Write-Host ""
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
    Write-Host "  Try running PowerShell as Administrator." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
