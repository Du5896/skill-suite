# -*- coding: utf-8 -*-
"""desktop-diary 辅助脚本：在桌面创建/追加带 emoji 的日记记事本。

用法:
    python diary.py --title "任务名" --summary "一句话摘要" [--mood "心情"] [--dir 目录] [--prefix 前缀] [--emoji ✅] [--dry-run] [--date YYYY-MM-DD]

默认行为:
    - 自动探测桌面(Windows %USERPROFILE%\\Desktop / OneDrive 桌面, macOS ~/Desktop, Linux ~/Desktop)
    - 按天文件: <前缀><YYYY-MM-DD>.txt, 默认前缀"日记-"
    - 文件已存在则追加(不覆盖旧内容), 不存在则创建
    - 输出为 UTF-8, 追加时不会破坏已有内容

--dry-run: 不写真实桌面, 把结果写到系统临时目录, 用于验证。
"""
import argparse
import datetime
import os
import sys
import tempfile

WEEKDAY_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def detect_desktop():
    """跨平台探测桌面路径。"""
    if sys.platform == "win32":
        profile = os.environ.get("USERPROFILE")
        if profile:
            plain = os.path.join(profile, "Desktop")
            # OneDrive 桌面优先: OneDrive/OneDriveCommercial 环境变量指向的桌面目录
            for var in ("OneDrive", "OneDriveCommercial"):
                od = os.environ.get(var)
                if od and os.path.isdir(od):
                    od_desktop = os.path.join(od, "Desktop")
                    # 仅当系统桌面目录不存在时, 认定用户桌面已重定向到 OneDrive
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


def build_entry(date_str, time_str, weekday, title, summary, mood, emoji):
    lines = [
        "📅 {} {}".format(date_str, weekday),
        "🕒 {} · {} 完成「{}」".format(time_str, emoji, title),
        "📝 摘要：{}".format(summary),
    ]
    if mood:
        lines.append("😊 心情：{}".format(mood))
    lines.append("────")
    return "\n".join(lines) + "\n\n"


def main():
    parser = argparse.ArgumentParser(description="桌面日记: 按天在桌面追加 emoji 风格记事本")
    parser.add_argument("--title", required=True, help="任务名/主题(必填)")
    parser.add_argument("--summary", required=True, help="一句话摘要(必填)")
    parser.add_argument("--mood", default="", help="心情词(可选)")
    parser.add_argument("--dir", default=None, help="目标目录(默认自动探测桌面)")
    parser.add_argument("--prefix", default="日记-", help="文件名前缀(默认'日记-')")
    parser.add_argument("--emoji", default="✅", help="条目表情(默认✅)")
    parser.add_argument("--dry-run", action="store_true", help="写入临时目录用于验证")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD(默认今天, 测试用)")
    args = parser.parse_args()

    if args.date:
        try:
            d = datetime.datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            sys.exit("日期格式错误, 应为 YYYY-MM-DD")
    else:
        d = datetime.datetime.now()

    date_str = d.strftime("%Y-%m-%d")
    time_str = d.strftime("%H:%M")
    weekday = WEEKDAY_CN[d.weekday()]

    if args.dry_run:
        target_dir = tempfile.mkdtemp(prefix="desktop-diary-dryrun-")
    elif args.dir:
        target_dir = args.dir
    else:
        target_dir = detect_desktop()

    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, "{}{}.txt".format(args.prefix, date_str))

    entry = build_entry(date_str, time_str, weekday, args.title, args.summary, args.mood, args.emoji)

    mode = "a"
    exists = os.path.exists(file_path)
    if exists:
        # 追加模式: 编码用 utf-8-sig, Python 读取时跳过已有 BOM, 写入不会重复加 BOM
        with open(file_path, "a", encoding="utf-8-sig", newline="\n") as f:
            f.write(entry)
    else:
        with open(file_path, "w", encoding="utf-8-sig", newline="\n") as f:
            f.write(entry)

    # 回读校验: 确认新条目已写入且旧内容未被破坏
    with open(file_path, "r", encoding="utf-8-sig") as f:
        content = f.read()
    if args.title not in content:
        sys.exit("校验失败: 新条目未出现在文件中, 请检查权限或路径")

    print("MODE:{}".format("DRY-RUN" if args.dry_run else "REAL"))
    print("EXISTS_BEFORE:{}".format("yes" if exists else "no"))
    print("FILE:{}".format(file_path))
    print("VERIFY:ok")


if __name__ == "__main__":
    main()
