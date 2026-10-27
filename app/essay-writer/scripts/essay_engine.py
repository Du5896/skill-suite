# -*- coding: utf-8 -*-
"""essay_engine.py — 中文写作引擎（代码复刻版）

把"专业写作能力"中可程序化的部分全部复刻成代码：
  结构规划 / 字数配比 / 质量检查(字数·重复词·分段·表情·点题) / 桌面保存。

CLI 子命令：
  plan   --topic <主题> --words <目标字数> --style <文体> [--emoji on|off] [--scene <场景>]
         生成结构大纲 + 每段目标字数（写作前的施工图）
  check  --file <作文文件> [--topic <主题词>] [--words <目标字数>] [--emoji on|off]
         质量检查，逐项 PASS/FAIL + 修改建议（写完后自检）
  save   --title <标题> --file <作文文件> [--dir <目录>] [--dry-run]
         保存到桌面记事本（同名自动加序号不覆盖 / UTF-8 / 回读校验）

示例：
  python essay_engine.py plan --topic "那一刻，我长大了" --words 800 --style 记叙文 --emoji on
  python essay_engine.py check --file essay.txt --topic "成长" --words 800 --emoji on
  python essay_engine.py save --title "那一刻，我长大了" --file essay.txt
"""
import argparse
import datetime
import json
import os
import re
import sys
import tempfile

# ============ 写作方法论知识库（代码内嵌，LLM 直接引用） ============

STYLES = {
    "记叙文": {
        "desc": "凤头(场景/悬念/对话切入) → 起因 → 经过(详写细节) → 高潮 → 结果+感悟升华",
        "segments": [
            ("开头·凤头", "场景/悬念/对话切入，画面感第一句，抛出人物或事件"),
            ("起因", "交代时间地点人物，事件为什么发生"),
            ("经过·详写", "写具体过程，用细节/动作/神态/心理，至少两处修辞"),
            ("高潮", "冲突或情感最强烈处，节奏放慢，描写放大"),
            ("结尾·豹尾", "呼应开头，点题 + 一句感悟升华，留余味"),
        ],
        "weights": [0.12, 0.14, 0.32, 0.22, 0.20],
    },
    "议论文": {
        "desc": "引论(现象/名言引入+亮观点) → 本论(2-3 分论点，各举例+分析) → 结论(重申+展望)",
        "segments": [
            ("引论", "现象或名言引入，亮明中心论点（一句话）"),
            ("分论点一", "论点 + 典型事例 + 因果分析"),
            ("分论点二", "论点 + 典型事例 + 因果分析"),
            ("分论点三", "论点 + 反例或对比 + 分析（或让步转折）"),
            ("结论", "重申观点，联系现实，展望或呼吁"),
        ],
        "weights": [0.14, 0.22, 0.22, 0.22, 0.20],
    },
    "说明文": {
        "desc": "总述特征 → 分点说明(数据/分类/顺序) → 小结",
        "segments": [
            ("总述", "介绍说明对象及其最突出特征"),
            ("分点一", "一个方面：数据/过程/性质"),
            ("分点二", "一个方面：数据/过程/性质"),
            ("分点三", "一个方面：数据/过程/性质"),
            ("小结", "总结特征，点明意义或用途"),
        ],
        "weights": [0.16, 0.22, 0.22, 0.22, 0.18],
    },
    "读后感": {
        "desc": "引(读了什么) → 议(亮观点) → 联(联系实际) → 结(升华)",
        "segments": [
            ("引", "交代读了什么书/文，概述触动自己的点"),
            ("议", "亮明核心观点，结合原文情节论证"),
            ("联", "联系自身经历或现实生活，谈共鸣与改变"),
            ("结", "总结升华，回到原书给人带来的力量"),
        ],
        "weights": [0.16, 0.28, 0.32, 0.24],
    },
    "演讲稿": {
        "desc": "开场(问候+引入) → 观点展开(2-3 层) → 结尾(呼吁/激励)",
        "segments": [
            ("开场", "问候听众，用故事/问题/数据引入话题"),
            ("观点一", "第一个层次，事例 + 论证"),
            ("观点二", "第二个层次，事例 + 论证"),
            ("观点三", "第三个层次，事例 + 论证"),
            ("结尾", "回扣主题，发出呼吁或寄语"),
        ],
        "weights": [0.14, 0.22, 0.22, 0.22, 0.20],
    },
    "散文": {
        "desc": "起(场景/物象) → 承(展开铺陈) → 转(感悟) → 合(呼应升华)",
        "segments": [
            ("起", "由一物/一景/一事起笔，画面感强"),
            ("承", "铺陈展开，多角度描写与联想"),
            ("转", "由物及理，触景生情，亮出感悟"),
            ("合", "收束全文，呼应开头，余韵悠长"),
        ],
        "weights": [0.18, 0.30, 0.28, 0.24],
    },
}

STYLE_DEFAULT = "记叙文"

# 语言八锦（每篇至少用 3 种）
RHETORIC = ["比喻", "排比", "拟人", "对比", "引用(名言/诗句)", "设问", "对偶", "细节白描"]

# 表情包点缀规范
EMOJI_POOL = {
    "writing": "✏️", "note": "📝", "done": "🎉", "highlight": "🌟",
    "idea": "💡", "heart": "❤️", "process": "⏳", "goal": "🏆",
}

# emoji 字符范围（用于数量统计）
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F0FF\U0001F900-\U0001F9FF"
    "\U00002600-\U000027BF\U00002B00-\U00002BFF\U00002190-\U000021FF"
    "\U0000FE00-\U0000FE0F\U0000200D\U000020E3]"
)

PUNCT_RE = re.compile(r"[\s，。！？；：、,.!?;:'\"“”‘’（）()《》【】—…·～~\-]")

REPEAT_PATTERNS = [
    (re.compile(r"([\u4e00-\u9fff]{2,})\1"), "相邻重复词（如'但是但是'）"),
    (re.compile(r"的的|了了|是是|在在|和和|很很"), "单字重复堆叠"),
]


def detect_desktop():
    """跨平台探测桌面路径（Windows/OneDrive/macOS/Linux）。"""
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE")
        if profile:
            plain = os.path.join(profile, "Desktop")
            for var in ("OneDrive", "OneDriveCommercial"):
                od = os.environ.get(var)
                if od and os.path.isdir(od):
                    od_desktop = os.path.join(od, "Desktop")
                    if os.path.isdir(od_desktop) and not os.path.isdir(plain):
                        return od_desktop
            if os.path.isdir(plain):
                return plain
        return os.path.join(os.path.expanduser("~"), "Desktop")
    home = os.path.expanduser("~")
    for candidate in (os.path.join(home, "Desktop"), home):
        if os.path.isdir(candidate):
            return candidate
    return home


def unique_path(directory, base_name):
    """同名自动加序号，返回不存在的路径（绝不覆盖旧文件）。"""
    candidate = os.path.join(directory, base_name)
    n = 2
    while os.path.exists(candidate):
        root, ext = os.path.splitext(base_name)
        candidate = os.path.join(directory, "{}-{}{}".format(root, n, ext))
        n += 1
    return candidate


def read_text(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


# ============ 子命令 plan：结构大纲 + 字数配比 ============

def cmd_plan(args):
    style = args.style if args.style in STYLES else STYLE_DEFAULT
    if args.style not in STYLES:
        print("WARN: 未知文体 '{}'，已回退为 '{}'（可选：{}）".format(
            args.style, style, "/".join(STYLES.keys())))
    words = max(100, int(args.words))
    tmpl = STYLES[style]
    segs = tmpl["segments"]
    weights = tmpl["weights"]
    # 按权重分配每段目标字数
    allocs = [max(30, int(round(words * w))) for w in weights]
    # 校正总和到目标字数
    diff = words - sum(allocs)
    allocs[-1] = max(30, allocs[-1] + diff)

    lines = [
        "=== 写作施工图 ===",
        "文体：{} ｜ 目标字数：{} ｜ 表情包：{}".format(style, words, "开" if args.emoji == "on" else "关"),
        "结构要点：{}".format(tmpl["desc"]),
        "---",
    ]
    for i, ((role, hint), alloc) in enumerate(zip(segs, allocs), 1):
        lines.append("{}. {}（约 {} 字）：{}".format(i, role, alloc, hint))
    lines.append("---")
    lines.append("语言要求：{} 至少用 3 种。".format("、".join(RHETORIC)))
    if args.emoji == "on":
        lines.append("表情包：全篇 3-6 个（标题后 1、重点句后 0-1、结尾 1），点缀不喧宾夺主；"
                     "正式/考试场景默认不加。")
    out = "\n".join(lines)
    print(out)
    if args.json:
        print("\n---JSON---")
        print(json.dumps({
            "style": style, "words": words, "emoji": args.emoji,
            "segments": [{"role": r, "hint": h, "target": a}
                         for (r, h), a in zip(segs, allocs)],
        }, ensure_ascii=False))


# ============ 子命令 check：质量检查 ============

def cmd_check(args):
    if not os.path.isfile(args.file):
        sys.exit("文件不存在: {}".format(args.file))
    text = read_text(args.file)
    body = text.strip()
    target = int(args.words) if args.words else None

    # 标题行（《...》单独成段）不参与正文统计与点题检查
    title_line = None
    paras_raw = [p for p in body.split("\n\n") if p.strip()]
    if paras_raw and paras_raw[0].startswith("《") and "》" in paras_raw[0] \
            and "\n" not in paras_raw[0]:
        title_line = paras_raw[0]
        paras_raw = paras_raw[1:]
        body = "\n\n".join(paras_raw)

    # 1 字数
    char_total = len(re.sub(r"\s", "", body))
    char_no_punct = len(PUNCT_RE.sub("", body))
    report = []
    if target:
        low, high = int(target * 0.9), int(target * 1.1)
        ok = low <= char_total <= high
        report.append(("字数(目标 {})".format(target), "PASS" if ok else "FAIL",
                       "实际 {} 字(去空白，含标点)；不含标点 {} 字".format(char_total, char_no_punct),
                       "需扩写细节/事例" if char_total < low else ("需删减重复句" if char_total > high else "")))
    else:
        report.append(("字数", "INFO", "共 {} 字(含标点)".format(char_total), ""))

    # 2 重复词/口语病
    rep_issues = []
    for pat, label in REPEAT_PATTERNS:
        m = pat.search(body)
        if m:
            rep_issues.append(label + "：「{}」".format(m.group(0)))
    report.append(("重复词/口语病", "FAIL" if rep_issues else "PASS",
                   "；".join(rep_issues) if rep_issues else "未发现相邻重复堆叠",
                   "删掉重复堆叠，换同义表达" if rep_issues else ""))

    # 3 段落数
    paras = [p for p in body.split("\n\n") if p.strip()]
    n_paras = len(paras)
    report.append(("分段", "PASS" if 3 <= n_paras <= 8 else "WARN",
                   "共 {} 段".format(n_paras),
                   "目标 3-8 段；一段超过 4 行建议再分" if not (3 <= n_paras <= 8) else ""))

    # 4 emoji 数量
    n_emoji = len(EMOJI_RE.findall(body))
    if args.emoji == "on":
        ok = 3 <= n_emoji <= 6
        report.append(("表情包数量", "PASS" if ok else "WARN",
                       "共 {} 个（规范 3-6 个）".format(n_emoji),
                       "重点句后各加 0-1 个，结尾加 1 个" if n_emoji < 3 else ("删到 6 个以内" if n_emoji > 6 else "")))
    else:
        report.append(("表情包数量", "PASS" if n_emoji == 0 else "WARN",
                       "共 {} 个（要求不加）".format(n_emoji), "移除表情包" if n_emoji else ""))

    # 5 点题（主题词出现在正文开头段与结尾段）
    if args.topic:
        topic = args.topic.strip()
        first_ok = topic in paras_raw[0] if paras_raw else False
        last_ok = topic in paras_raw[-1] if paras_raw else False
        ok = first_ok and last_ok
        report.append(("点题('{}')".format(topic), "PASS" if ok else "FAIL",
                       "开头{}出现 / 结尾{}出现".format("已" if first_ok else "未",
                                                        "已" if last_ok else "未"),
                       "开头段或结尾段补入主题词，首尾呼应" if not ok else ""))

    # 6 金句/修辞（提示项，不做硬判断）
    has_colon = "：" in body or "——" in body
    report.append(("亮点句", "INFO" if has_colon else "HINT",
                   "检测到破折号/冒号引出的重点句" if has_colon else "建议至少 1 句金句（用冒号或破折号引出）",
                   ""))

    print("=== 质量检查报告 ===")
    any_fail = False
    for name, status, detail, advice in report:
        any_fail = any_fail or status == "FAIL"
        print("[{}] {}｜{}".format(status, name, detail))
        if advice:
            print("     建议：{}".format(advice))
    print("结论：{}".format("未达标，需修改后重新检查" if any_fail else "达标，可保存交付"))
    if args.json:
        print("---JSON---")
        print(json.dumps([{"item": n, "status": s, "detail": d, "advice": a}
                          for n, s, d, a in report], ensure_ascii=False))


# ============ 子命令 save：保存到桌面记事本 ============

def cmd_save(args):
    body = read_text(args.file) if args.file else ""
    if args.title:
        body = "《{}》\n\n{}".format(args.title.strip(), body.strip())
    if not body.strip():
        sys.exit("没有可保存的内容（--title 和 --file 都为空）")

    if args.dry_run:
        target_dir = tempfile.mkdtemp(prefix="essay-engine-dryrun-")
    elif args.dir:
        target_dir = args.dir
    else:
        target_dir = detect_desktop()
    os.makedirs(target_dir, exist_ok=True)

    today = datetime.date.today().strftime("%Y-%m-%d")
    file_path = unique_path(target_dir, "作文-{}.txt".format(today))

    with open(file_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(body.rstrip() + "\n")

    # 回读校验
    saved = read_text(file_path)
    if args.title and args.title.strip() not in saved:
        sys.exit("校验失败: 标题未出现在文件中")
    print("MODE:{}".format("DRY-RUN" if args.dry_run else "REAL"))
    print("FILE:{}".format(file_path))
    print("VERIFY:ok")


# ============ 入口 ============

def main():
    parser = argparse.ArgumentParser(description="中文写作引擎（代码复刻版）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="生成结构大纲与每段目标字数")
    p_plan.add_argument("--topic", required=True)
    p_plan.add_argument("--words", type=int, default=800)
    p_plan.add_argument("--style", default=STYLE_DEFAULT,
                        choices=list(STYLES.keys()))
    p_plan.add_argument("--emoji", choices=["on", "off"], default="on")
    p_plan.add_argument("--scene", default="学生作文")
    p_plan.add_argument("--json", action="store_true")
    p_plan.set_defaults(func=cmd_plan)

    p_check = sub.add_parser("check", help="质量检查：字数/重复/分段/表情/点题")
    p_check.add_argument("--file", required=True)
    p_check.add_argument("--topic", default=None)
    p_check.add_argument("--words", type=int, default=None)
    p_check.add_argument("--emoji", choices=["on", "off"], default="on")
    p_check.add_argument("--json", action="store_true")
    p_check.set_defaults(func=cmd_check)

    p_save = sub.add_parser("save", help="保存到桌面记事本（不重名/UTF-8/回读校验）")
    p_save.add_argument("--title", required=True)
    p_save.add_argument("--file", required=True)
    p_save.add_argument("--dir", default=None)
    p_save.add_argument("--dry-run", action="store_true")
    p_save.set_defaults(func=cmd_save)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
