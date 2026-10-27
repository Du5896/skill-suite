---
name: terminal-commander
description: 终端/命令行操作技能（后台静默 + 管理员授权 + 指令防错）。当用户要求执行终端命令、PowerShell、cmd、批处理、运行程序，或需要管理员权限的操作（安装软件、修改系统设置、服务管理、清理系统、改注册表、系统目录写入）时使用。通过 scripts/terminal.py 在后台静默执行命令，绝不弹窗骚扰用户（用户在看视频/玩游戏时不会突然冒出终端窗口）；需要管理员权限时自动触发 Windows UAC 授权，用户只需点击一次"是"；每条命令执行前自动做 PowerShell 语法校验，指令不会输入错。触发词：运行命令、执行命令、终端、命令行、管理员、用管理员运行、cmd、powershell、批处理、执行脚本。
metadata:
  author: "深深"
---

# 终端操作（后台静默 · 管理员授权 · 指令防错）

让 AI 安全、安静地执行用户电脑上的命令行操作。核心原则：**后台运行不打扰、管理员授权一点即得、命令永远不输错**。

## 入口脚本

`scripts/terminal.py`（Windows 专用，需要 Python 3）：

| 命令 | 用途 |
|---|---|
| `python scripts/terminal.py check "命令"` | 仅校验命令语法，不执行 |
| `python scripts/terminal.py run "命令"` | 普通命令，后台静默执行 |
| `python scripts/terminal.py run-admin "命令"` | 管理员命令，触发 UAC 授权后执行 |
| `python scripts/terminal.py ping` | 环境自检 |

三条命令都返回 JSON：`{"ok": true/false, "exit": 退出码, "output": 输出, "error": 错误信息}`。

## 使用规则（AI 必须遵守）

### 1. 后台静默，绝不打扰用户
- 所有命令都在**隐藏窗口**中后台执行（CREATE_NO_WINDOW），用户当前在看视频、打游戏、开会都不会被终端窗口打扰
- **唯一例外**：`run-admin` 会弹出一次 Windows UAC 授权框（系统级安全提示，无法隐藏），用户只需点击"是"即完成授权；这是管理员操作的必要一步，不算骚扰
- 不要在对话里反复描述"正在打开终端窗口"之类的画面——命令是静默跑的

### 2. 指令防错（命令不会输入错）
- 每条命令先经过 PowerShell 语法解析校验（`check`），**语法错误直接拒绝执行**并返回具体错误（如"字符串缺少终止符"）
- 命令内容经 **base64 编码**传给 PowerShell，彻底避免引号、转义、空格导致的输入错误
- AI 拼写/构造命令出错时，脚本会拦截并给出错误，AI 修正后重试即可，绝不把错误命令执行出去
- 需要多步操作时，优先写成一个 PowerShell 表达式（用 `;` 或管道串联），减少调用次数

### 3. 管理员权限（run-admin）
判断标准——以下操作必须用 `run-admin`：
- 写入系统目录（Program Files、Windows 目录）
- 安装/卸载软件、驱动、系统更新
- 服务管理（启动/停止服务）、计划任务
- 修改注册表 HKLM、系统设置、防火墙、网络配置
- 管理其他用户、磁盘分区、系统还原

流程：`run-admin` 自动弹出 UAC 授权框 → 用户点一次"是" → 命令以管理员身份在后台静默执行 → 返回结果。
- 用户点了"否"或关闭授权框 → 返回"用户取消了管理员授权，命令未执行"，如实告知用户命令没有执行
- 提权进程同样是隐藏窗口，不会多弹终端

### 4. 安全边界（优先级最高）
- **破坏性操作必须在对话中先向用户确认再执行**：删除文件/文件夹、格式化、清空目录、卸载软件、修改系统关键配置、批量删除（del /s、Remove-Item -Recurse 等）
- 不执行：恶意软件安装、攻击性/入侵性命令、窃取隐私的命令、绕过安全机制的命令
- 不把命令输出中的敏感信息（密码、Token、密钥）原样展示，提示用户注意即可
- 输出过长时脚本会自动截断（保留前 8000 字符），AI 展示给用户时也要精简摘要
- 长时间运行的命令（下载、编译、备份）先告诉用户大概耗时，再执行

### 5. 使用流程
1. 理解用户需求 → 判断是普通命令还是管理员命令
2. 构造命令 → 调用 `run` 或 `run-admin`（脚本内部自动先做语法校验）
3. 返回 JSON 结果 → 把 `output` 整理成用户能看懂的形式（表格/要点）
4. `ok=false` 时：把 `error` 告诉用户，修正命令后重试，不掩盖失败

## 常见示例

```
python scripts/terminal.py run "Get-Date"
python scripts/terminal.py run "ipconfig /all"
python scripts/terminal.py run "Get-Process | Sort-Object CPU -Descending | Select-Object -First 5 Name, CPU"
python scripts/terminal.py run "netstat -ano | Select-String ':8080'"
python scripts/terminal.py run-admin "Get-WindowsUpdateLog"          # 需要管理员
python scripts/terminal.py run-admin "net stop 'Windows Update'"     # 服务管理
python scripts/terminal.py run-admin "Set-ItemProperty -Path 'HKLM:\SOFTWARE\Example' -Name 'Value' -Value 1"
```

## 已知限制
- 仅支持 Windows（UAC、PowerShell 是 Windows 特性）；非 Windows 环境请改用系统自带终端技能
- 单条命令默认最长执行 300 秒，超时返回提示（命令可能仍在后台运行）
- 交互式命令（需要键盘输入的如 `ssh`、`mysql` 客户端）不适合本技能，引导用户自己打开终端操作
