# 管理员权限设置定时任务（schtasks + /NP = 锁屏也能跑，不需要密码）
#Requires -RunAsAdministrator

$PythonExe = (Get-Command python).Source

# 删旧任务
schtasks /Delete /TN "StockRotationSignal" /F 2>$null
schtasks /Delete /TN "DCA_Monthly_Reminder" /F 2>$null

# 1. 持仓报告 — 每天 04:30  (/NP = no password, run when not logged on)
schtasks /Create /TN "StockRotationSignal" `
    /TR "`"$PythonExe`" `"C:\AI\cc\stock\code\rotation_signal.py`" --check-all --email" `
    /SC DAILY /ST 04:30 /NP /RL HIGHEST /F

# 2. DCA 提醒 — 每天 09:00
schtasks /Create /TN "DCA_Monthly_Reminder" `
    /TR "`"$PythonExe`" `"C:\AI\cc\stock\code\dca_monthly_reminder.py`"" `
    /SC DAILY /ST 09:00 /NP /RL HIGHEST /F

Write-Host ""
Write-Host "Done." -ForegroundColor Green
schtasks /Query /TN "StockRotationSignal" /FO LIST | Select-String "TaskName|Status|Schedule|Logon"
schtasks /Query /TN "DCA_Monthly_Reminder" /FO LIST | Select-String "TaskName|Status|Schedule|Logon"
