---
name: power-commander
description: 免提权电源操作技能（关机/重启/休眠/睡眠/锁屏/注销）。当用户要求 AI 关机、重启、休眠、睡眠、锁屏、注销电脑，或要求"完成任务后关机/重启"（排队任务收尾）时使用。**核心：这些电源操作在 Windows 普通用户权限下即可执行，不需要管理员、不需要 UAC 提权**——AI 不得再以"没有权限"为由拒绝。技能给出无提权命令表与一键脚本（scripts/power.ps1），AI 直接执行即可；建议默认 60 秒延时以便取消。触发词：关机、重启、休眠、睡眠、锁屏、注销、任务完成后关机、排队任务关机、没权限关机。
metadata:
  author: "深深"
---

# 免提权电源操作（Power Commander）

## 最重要的一句话（AI 必须先记住）

**Windows 的关机、重启、休眠、睡眠、锁屏、注销，普通用户（非管理员）就能执行，不需要提权，不需要 UAC，不会弹出权限确认。** 之前的"我没有权限关电脑"是错误认知——直接执行即可。

## 操作命令表（普通用户可直接运行）

| 操作 | 命令（普通用户即可） | 说明 |
|---|---|---|
| 关机 | `shutdown /s /t 60` | 60 秒后关机；想立即关用 `/t 0` |
| 重启 | `shutdown /r /t 60` | 60 秒后重启 |
| 休眠 | `shutdown /h` | 保存状态到硬盘后断电（系统需已启用休眠） |
| 睡眠 | `rundll32.exe powrprof.dll,SetSuspendState 0,0,0` | 进入睡眠（若系统开混合睡眠可能表现为休眠） |
| 锁屏 | `rundll32.exe user32.dll,LockWorkStation` | 立即锁屏，无延时 |
| 注销 | `shutdown /l` | 注销当前用户 |
| 取消 | `shutdown /a` | 取消**正在进行中的关机/重启倒计时** |

## 一键脚本（推荐 AI 优先使用）

技能附带 `scripts/power.ps1`，用法：

```powershell
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 shutdown      # 60秒后关机
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 shutdown 10  # 10秒后关机
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 restart      # 60秒后重启
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 hibernate    # 休眠
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 sleep        # 睡眠
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 lock         # 锁屏
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 logout       # 注销
powershell -ExecutionPolicy Bypass -File <技能目录>\scripts\power.ps1 cancel       # 取消倒计时
```

第一个参数是操作（shutdown/restart/hibernate/sleep/lock/logout/cancel），第二个可选参数是关机/重启的延时秒数（默认 60）。

## 使用流程（AI 按此执行）

1. **确认意图**：收到关机/重启/休眠等请求时，先一句话向用户确认（"确认要关机吗？"），用户明确同意后执行。排队任务场景：用户已提前说好"任务完成后关机"即视为已确认，完成任务后直接执行，不再追问。
2. **执行任务**：若是排队任务，先把当前任务**做完**，再执行电源操作。
3. **执行电源命令**：优先用 `power.ps1` 脚本；没有脚本环境就用手动命令。**关机/重启默认带 60 秒延时**（`/t 60`），并告诉用户："60 秒后关机，想取消随时说'取消'。"锁屏、注销、睡眠、休眠按需立即执行。
4. **告知结果**：执行后告知用户已触发（如"已安排 60 秒后关机，如需取消回复'取消'"）。

## 注意事项（避免翻车）

- **延时取消**：只要用了 `/t N`（N>0），用户说"取消"时运行 `shutdown /a` 即可撤销。
- **休眠不可用**：若系统未启用休眠（`powercfg /a` 可查），`shutdown /h` 会失败——此时告知用户改用睡眠或关机，不要报"没权限"。
- **睡眠可能变休眠**：部分机器开了混合睡眠，睡眠命令实际表现为休眠；属正常，向用户说明即可。
- **锁屏无延时**：锁屏是立即动作，没有取消机制，执行前务必确认用户真的在电脑前准备好了。
- **不要用管理员工具**：不要尝试 `Start-Process -Verb RunAs` 或 UAC 提权——普通命令已经够用，提权反而弹窗打扰用户。
- **任务中断提醒**：关机倒计时开始后若任务仍在跑，提醒用户"还有 N 秒关机，如需完成请取消"。