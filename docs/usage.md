# 使用说明

## 一、导入技能包

每个技能包是自包含目录，导入方式因平台而异：

1. 下载仓库 Release 中的 zip，或直接复制 `app/<技能名>/` 目录。
2. 放入目标平台的技能库目录（不同平台目录位置不同，一般为用户目录下的 `skills` / `.user_skills` 等）。
3. 平台自动读取 `SKILL.md` 元信息，之后按场景触发。

`docs/技能清单.md` 记录了全部 12 个技能包的功能与维护时间，可作为导入索引。

## 二、独立运行核心脚本

`core/` 下的脚本不依赖技能平台，可直接运行：

```bash
# 文件预览（解析并输出 Markdown）
python core/file_preview.py <文件路径>

# 本地端口桥接服务（监听 127.0.0.1:58201）
python core/bridge_server.py

# 桌面日记引擎
python core/diary.py

# 写作引擎（生成 + 保存）
python core/essay/essay_engine.py
python core/essay/essay_save.py
```

PowerShell 脚本：

```powershell
# 免提权电源操作（默认 60 秒延时可取消）
powershell -ExecutionPolicy Bypass -File core/power.ps1 shutdown

# 管理员提权运行器
powershell -ExecutionPolicy Bypass -File core/terminal/admin_runner.ps1 <命令>
```

## 三、技能清单速览

| 技能 | 能力 |
| --- | --- |
| desktop-diary | 桌面日记，任务收尾自动记录，带 emoji |
| essay-writer | 写作：先问字数/主题/文体，成文存桌面记事本 |
| agent-roleplay | 智能体扮演，全量记忆，22 个角色模板 |
| dog-sim | 模拟养狗（可卡布），525 个偶发事件，华为全家桶背景 |
| terminal-commander | 后台静默终端 + 一键 UAC 提权 |
| file-preview | 跨平台文件真实解析（零第三方依赖） |
| file-master | 文件处理中心：PPT/预览/合同/Word/去 AI 味 |
| animation-ui-master | 动画与 UI 设计，1707 条动画百科 + 9205 条应用映射 |
| animation-ui-table | 表格驱动的动画/UI 设计（内置 file-preview） |
| local-port-computer-bridge | 本地端口电脑操作桥接（仅本机回环） |
| name-setter | 称呼定制：AI 名字 / 对你的称呼 / 人格 |
| power-commander | 免提权关机/重启/休眠/睡眠/锁屏/注销 |

## 四、安全边界

- 本地端口桥接仅监听 `127.0.0.1`，不开放外网；高危操作必须显式确认。
- 终端执行器仅执行用户明确要求的命令，不做额外系统改动。
- 电源操作默认带 60 秒延时，误触可取消。
