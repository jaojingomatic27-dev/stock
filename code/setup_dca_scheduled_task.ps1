# DCA 定投提醒定时任务
# 每天 09:00 运行 dca_monthly_reminder.py
# 脚本内部自动判断是否为定投日(1号+7天)或RSI跟进日(定投后7天)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$PyScript = Join-Path $ScriptDir "dca_monthly_reminder.py"
$PythonExe = (Get-Command python).Source

$TaskName = "DCA_Monthly_Reminder"
$Action = New-ScheduledTaskAction -Execute $PythonExe `
    -Argument "`"$PyScript`"" `
    -WorkingDirectory $ProjectDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"

$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive -RunLevel Limited

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

$Task = Register-ScheduledTask -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "DCA 每月定投提醒 + RSI跟进。每天09:00运行，脚本内部判断是否为定投日。" `
    -Force

if ($Task) {
    Write-Host "✅ 定时任务已创建: $TaskName" -ForegroundColor Green
    Write-Host "   触发时间: 每天 09:00" -ForegroundColor Gray
    Write-Host "   脚本: $PyScript" -ForegroundColor Gray
    Write-Host ""
    Write-Host "📋 任务详情:" -ForegroundColor Yellow
    Write-Host "   - 每天 09:00 运行，自动判断是否为 1号+7天 定投日" -ForegroundColor Gray
    Write-Host "   - 定投日后约 7 天自动发 RSI 跟进邮件" -ForegroundColor Gray
    Write-Host "   - 非定投日/非跟进日静默退出" -ForegroundColor Gray
    Write-Host ""
    Write-Host "🔧 管理命令:" -ForegroundColor Yellow
    Write-Host "   查看: Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "   运行: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "   禁用: Disable-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
    Write-Host "   删除: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Gray
    Write-Host "   测试: python `"$PyScript`" --force --dry-run" -ForegroundColor Gray
} else {
    Write-Host "❌ 任务创建失败" -ForegroundColor Red
}
