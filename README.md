# Skill Suite

一套面向 AI 智能体（Agent）的技能包集合，覆盖写作、角色扮演、文件处理、动画设计、系统操作等常见场景。

每个技能包都是一个自包含目录：`SKILL.md` 描述能力与使用方式，`scripts/` 放确定性脚本，`references/` 放资料库与规范，必要时内置子技能。导入即可扩展 AI 的能力边界，无需额外配置。

## 项目结构

本项目分两部分：

- **core/**：纯核心逻辑，不含界面。各技能底层的独立引擎脚本——本地端口桥接服务、文件解析器、记忆系统、写作引擎、终端与电源操作脚本等。可直接运行，也可作为库被其他脚本引用。
- **app/**：带完整交互的技能包。每个技能一个目录，包含 `SKILL.md` 与配套资源，按平台规范导入技能库即可使用。

另有 `model/`（知识数据）、`train/`（训练脚本，当前为占位）、`docs/`（架构设计与使用说明）、`screenshots/`（运行截图）。

## 开箱即用

> **这个仓库可以直接导入使用，不需要像一些国外项目那样手动补文件。**
> `app/` 下的每个技能包都是**完整自包含**的：`SKILL.md`（能力说明）+ `scripts/`（可执行脚本）+ `references/`（资料库与规范）+ `bundled/`（内置子技能）全都打包在一起。把技能目录（或 Release 里的 zip）放进 AI 平台的技能库，解压即用，**不用改任何配置、不用补任何依赖**。作者把每个包都维护成了成品，导入体验很省心。

## 快速开始

1. 导入技能：将 `app/<技能名>/` 整个目录（或仓库 Release 里的对应 zip）放入你的 AI 平台的技能库目录。
2. 独立运行核心脚本：`python core/bridge_server.py`、`python core/file_preview.py <文件>` 等，见 `docs/usage.md`。
3. 查阅各技能能力：见 `docs/技能清单.md`。

## 技术栈

| 组件 | 技术 |
| --- | --- |
| 核心引擎 | Python 3（标准库为主，零第三方依赖） |
| 终端 / 电源操作 | PowerShell 5.1+ |
| 动画知识库 | CSV 数据集 + Markdown 规范 |
| 文档处理 | openpyxl / python-docx（可选依赖） |
| 支持平台 | Windows / macOS / Linux |

## 目录树

```text
skill-suite/
├── core/                      # 纯核心逻辑（无 UI）
│   ├── bridge_server.py       # 本地端口桥接服务
│   ├── file_preview.py        # 文件解析器（xlsx/pptx/docx/pdf/csv）
│   ├── diary.py               # 桌面日记引擎
│   ├── power.ps1              # 免提权电源操作
│   ├── essay/                 # 写作引擎
│   ├── memory/                # 记忆系统（角色扮演 / 养狗模拟）
│   └── terminal/              # 终端执行器 + 管理员提权
├── app/                       # 完整技能包（带交互）
│   ├── desktop-diary/
│   ├── essay-writer/
│   ├── agent-roleplay/
│   ├── dog-sim/
│   ├── terminal-commander/
│   ├── file-preview/
│   ├── file-master/           # 内置 5 个子技能
│   ├── animation-ui-master/   # 内置 2 个子技能 + 动画资料库
│   ├── animation-ui-table/
│   ├── local-port-computer-bridge/
│   ├── name-setter/
│   └── power-commander/
├── model/                     # 知识数据（动画资料库等）
├── train/                     # 训练脚本（占位说明）
├── docs/                      # 架构设计 / 使用说明 / 技能清单
├── screenshots/               # 运行截图
├── .github/ISSUE_TEMPLATE/    # Issue 模板
├── README.md
├── LICENSE
├── requirements.txt
├── .gitignore
├── CHANGELOG.md
├── CONTRIBUTING.md
└── CODE_OF_CONDUCT.md
```

## 许可

[MIT License](LICENSE)，署名：深深
