# 架构设计

## 总体设计

本仓库是一套 AI 技能包集合。每个技能包遵循同一结构，导入后由 AI 平台按 `SKILL.md` 的元信息自动发现与触发。

技能包标准结构：

```text
<skill>/
├── SKILL.md              # 能力描述 + 使用流程（导入后由平台读取）
├── scripts/              # 确定性脚本（Python / PowerShell）
├── references/           # 资料库、规范、模板（按需读取）
└── bundled/              # 内置子技能（可选，实现多技能嵌套）
```

## 目录划分

| 目录 | 内容 | 边界 |
| --- | --- | --- |
| `core/` | 各技能的底层引擎脚本 | 纯逻辑，无 UI，可独立运行 |
| `app/` | 完整技能包 | 含 `SKILL.md` 与交互定义，直接导入 |
| `model/` | 知识数据 | 动画资料库等结构化数据，作为技能的知识权重 |
| `train/` | 训练脚本 | 当前为占位说明，后续扩展 |
| `docs/` | 文档 | 架构设计、使用说明、技能清单 |
| `screenshots/` | 截图 | 各技能运行效果图 |

## 核心模块

### 记忆系统（core/memory/）

角色扮演与养狗模拟共用同一套记忆设计：全量记录用户原话，按会话持久化，跨会话恢复。`roleplay_memory.py` 服务角色扮演，`dog_memory.py` 服务养狗模拟，两者互不干扰。

### 文件解析（core/file_preview.py）

纯标准库实现的通用文件解析器：支持 xlsx/xls（含旧版 OLE2+BIFF8 二进制）、csv、pptx/docx（XML 解包）、pdf（文本流提取）、文本与图片元信息。输出统一为 Markdown，供 AI 直接阅读。

### 终端与电源（core/terminal/、core/power.ps1）

终端执行器以隐藏窗口后台运行，命令先做语法校验再执行；需要管理员权限时触发 UAC 授权。电源脚本利用 Windows 原生 `shutdown` / `rundll32` 能力，普通用户权限即可完成关机、重启、休眠等操作。

### 本地端口桥接（core/bridge_server.py）

监听本机回环 `127.0.0.1:58201`，接收固定格式指令（`类别|动作|参数`）执行文件与程序操作。仅限本机、仅限本人，高危操作需 `CONFIRMED:` 标记。

### 写作引擎（core/essay/）

按字数配比生成结构大纲，成文后做质量检查并保存。`essay_engine.py` 负责生成，`essay_save.py` 负责落盘。

### 动画知识库（model/）

动画资料库共 1707 条动画类型百科（40 大类）与 9205 条界面应用映射，配套动效 Token 规范。技能按“能有动画的就要有动画”原则组合编排。

## 数据流

```text
用户请求 → 平台按 description 命中技能 → 读取 SKILL.md
  → 按流程调用 scripts / 读取 references → 产出结果
  → 需要文件解析时走 file_preview；需要持久化时走 memory
```
