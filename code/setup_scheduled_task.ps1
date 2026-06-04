# ============================================================
# Windows 定时任务：每天美股收盘后运行 rotation_signal.py
# ============================================================
# 用法（以管理员身份运行 PowerShell）：
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1
#
# 或直接运行自动检测：
#   powershell -ExecutionPolicy Bypass -File code\setup_scheduled_task.ps1
# ============================================================

param(
    [string]$Mode = "install",    # install / uninstall / status
    [string]$Time = "04:30",      # UTC 时间（美东 16:30 = 夏令时 UTC 20:30)
    [switch]$SendEmail = $false   # 是否发邮件
)

$TaskName = "StockRotationSignal"
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "ERROR: 找不到 Python。请确保 Python 在 PATH 中。" -ForegroundColor Red
    exit 1
}

$ScriptPath = Join-Path (Get-Location) "code\rotation_signal.py"
$EmailFlag = if ($SendEmail) { " --email" } else { "" }
$Action = "$PythonPath `"$ScriptPath`" --check$EmailFlag"

# ============================================================
# STATUS
# ============================================================
if ($Mode -eq "status") {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  定时任务状态" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""

    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "  任务: $TaskName" -ForegroundColor Green
        Write-Host "  状态: $($task.State)" -ForegroundColor $(if($task.State -eq 'Ready'){'Green'}else{'Yellow'})
        Write-Host "  触发器: $($task.Triggers | ForEach-Object { $_.ToString() })"
        Write-Host "  上次运行: $($task.LastRunTime)"
        Write-Host "  上次结果: $($task.LastTaskResult)"

        # 查询最近运行历史
        Write-Host ""
        Write-Host "  最近运行历史:" -ForegroundColor Gray
        $events = Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 5 -ErrorAction SilentlyContinue |
            Where-Object { $_.Message -match $TaskName }
        foreach ($evt in $events) {
            Write-Host "    $($evt.TimeCreated) - $($evt.Message.Split([Environment]::NewLine)[0])" -ForegroundColor Gray
        }
    } else {
        Write-Host "  任务未安装。运行: setup_scheduled_task.ps1" -ForegroundColor Yellow
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
        Write-Host "  ✅ 已删除定时任务: $TaskName" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  任务不存在: $TaskName" -ForegroundColor Yellow
    }
    Write-Host ""
    exit 0
}

# ============================================================
# INSTALL
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  安装定时任务: 三股轮动持仓监控" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Python:     $PythonPath"
Write-Host "  脚本:       $ScriptPath"
Write-Host "  执行时间:   每天 $Time (当地时间)"
Write-Host "  发邮件:     $(if($SendEmail){'是'}else{'否（仅终端输出）'})"
Write-Host "  命令:       $Action"
Write-Host ""

# 删除旧任务
$old = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($old) {
    Write-Host "  删除旧任务..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# 创建新任务
$Action = New-ScheduledTaskAction -Execute $PythonPath `
    -Argument "`"$ScriptPath`" --check$EmailFlag" `
    -WorkingDirectory (Get-Location).Path

$Trigger = New-ScheduledTaskTrigger -Daily -At $Time

# 任务配置：不强制唤醒，不重复，失败后重试 3 次间隔 30 分钟
$Settings = New-ScheduledTaskSettingsSet `
    -WakeToRun:$false `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 30)

# 以当前用户身份运行
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

try {
    Register-ScheduledTask -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Principal $Principal `
        -Description "每天美股收盘后检查三股Turbo权证轮动信号" `
        -Force | Out-Null

    Write-Host "  ✅ 定时任务已安装!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  ┌─────────────────────────────────────────────┐"
    Write-Host "  │  任务名:  $TaskName"
    Write-Host "  │  每天:    $Time (当地时间)"
    Write-Host "  │  命令:    python code\rotation_signal.py --check"
    Write-Host "  │  日志:    事件查看器 → 任务计划程序"
    Write-Host "  │  管理:    taskschd.msc → 搜索 '$TaskName'"
    Write-Host "  │  测试:    python code\rotation_signal.py --check"
    Write-Host "  └─────────────────────────────────────────────┘"
    Write-Host ""
    Write-Host "  📧 发送邮件需额外配置:"
    Write-Host "     1. 复制 .env.template → .env"
    Write-Host "     2. 填写 Gmail 应用专用密码"
    Write-Host "     3. 重新运行: setup_scheduled_task.ps1 -SendEmail"
    Write-Host ""
} catch {
    Write-Host "  ❌ 安装失败: $_" -ForegroundColor Red
    Write-Host "  💡 试试以管理员身份运行 PowerShell" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
