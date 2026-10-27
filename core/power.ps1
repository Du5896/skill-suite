# power-commander 免提权电源操作脚本
# 用法:
#   powershell -ExecutionPolicy Bypass -File power.ps1 shutdown [秒数]
#   powershell -ExecutionPolicy Bypass -File power.ps1 restart [秒数]
#   powershell -ExecutionPolicy Bypass -File power.ps1 hibernate
#   powershell -ExecutionPolicy Bypass -File power.ps1 sleep
#   powershell -ExecutionPolicy Bypass -File power.ps1 lock
#   powershell -ExecutionPolicy Bypass -File power.ps1 logout
#   powershell -ExecutionPolicy Bypass -File power.ps1 cancel
# 说明: 全部操作普通用户权限即可执行, 无需管理员/UAC 提权。

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("shutdown", "restart", "hibernate", "sleep", "lock", "logout", "cancel")]
    [string]$Action,

    [int]$DelaySeconds = 60
)

try {
    switch ($Action) {
        "shutdown" {
            if ($DelaySeconds -lt 0) { $DelaySeconds = 0 }
            shutdown /s /t $DelaySeconds
            if ($DelaySeconds -gt 0) {
                Write-Host "已安排 $DelaySeconds 秒后关机; 取消请运行: shutdown /a"
            } else {
                Write-Host "已执行立即关机"
            }
        }
        "restart" {
            if ($DelaySeconds -lt 0) { $DelaySeconds = 0 }
            shutdown /r /t $DelaySeconds
            if ($DelaySeconds -gt 0) {
                Write-Host "已安排 $DelaySeconds 秒后重启; 取消请运行: shutdown /a"
            } else {
                Write-Host "已执行立即重启"
            }
        }
        "hibernate" {
            shutdown /h
            Write-Host "已执行休眠"
        }
        "sleep" {
            rundll32.exe powrprof.dll,SetSuspendState 0,0,0
            Write-Host "已执行睡眠"
        }
        "lock" {
            rundll32.exe user32.dll,LockWorkStation
            Write-Host "已执行锁屏"
        }
        "logout" {
            shutdown /l
            Write-Host "已执行注销"
        }
        "cancel" {
            shutdown /a
            Write-Host "已尝试取消关机/重启倒计时"
        }
    }
}
catch {
    Write-Error "执行失败: $($_.Exception.Message)"
    exit 1
}
