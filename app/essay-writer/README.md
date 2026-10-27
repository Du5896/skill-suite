# essay-writer 技能包 — 安装说明

专业级中文写作技能（引擎驱动版）。把专业写作能力程序化为写作引擎 `essay_engine.py`：
结构规划、字数配比、质量检查（字数/重复词/分段/表情/点题）、桌面保存全部由代码完成，
正文语言由 LLM 按方法论生成。

## 目录结构

```
essay-writer/
├── SKILL.md               # 技能指令（YAML frontmatter + 流程 + 方法论）
├── README.md              # 本说明
└── scripts/
    └── essay_engine.py    # 写作引擎（plan / check / save 三个子命令）
```

## 在 OpenClaw / QClaw 中安装

方式 A（工作区技能，最常用）：
1. 把整个 `essay-writer/` 目录放到 `~/.openclaw/workspace/skills/essay-writer/`
2. 若技能监视未开启，重启网关或开新会话
3. 检查是否加载：`openclaw skills list`

方式 B（个人技能，无需 Shell）：
1. 打开 插件 → 技能 → 我的技能
2. 导入本 `SKILL.md` bundle（目录或压缩包）
3. 查看保存的版本与激活结果，新开会话生效

## 使用方法

- 直接说："帮我写一篇 800 字作文，主题是 XXX" —— 技能会先问关键问题，再走完整流程；
- 或用斜杠命令显式调用：`/essay-writer`。

## 引擎命令速查（供技能内部调用，也可手动调试）

```bash
# 1) 生成写作施工图（结构 + 每段目标字数）
python scripts/essay_engine.py plan --topic "那一刻，我长大了" --words 800 --style 记叙文 --emoji on

# 2) 质量检查（写完后自检，FAIL 必须回改）
python scripts/essay_engine.py check --file 作文.txt --topic "长大" --words 800 --emoji on

# 3) 保存到桌面记事本（同名自动加序号，绝不覆盖）
python scripts/essay_engine.py save --title "那一刻，我长大了" --file 作文.txt
```

## 能力说明（代码复刻了什么）

| 能力 | 实现 |
|---|---|
| 文体结构规划 | STYLES 知识库：记叙/议论/说明/读后感/演讲稿/散文，每段角色 + 权重 |
| 字数控制 | 按权重分配每段目标字数，check 强制 ±10% |
| 质量检查 | 重复词/口语病、分段、表情包数量、首尾点题、亮点句 |
| 表情包点缀 | EMOJI_RE 统计 + 规范（3-6 个） |
| 桌面保存 | 跨平台探测桌面 + 不重名 + UTF-8 + 回读校验 |
| 方法论指令 | SKILL.md：语言八锦、润色清单、交互流程 |

版本：2.0.0 ｜ 作者：深深 ｜ 许可证：MIT
