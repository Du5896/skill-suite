# -*- coding: utf-8 -*-
"""essay-writer 辅助脚本：把写好的作文保存为桌面记事本(.txt)。

用法:
    python essay_save.py --title "作文标题" --file "作文内容文件.txt"
    python essay_save.py --title "作文标题" --content "作文全文……"

行为:
    - 自动探测桌面(Windows %USERPROFILE%\\Desktop / OneDrive 桌面, macOS ~/Desktop, Linux ~/Desktop)
    - 文件名: 作文-<YYYY-MM-DD>.txt; 同名已存在则自动加序号(作文-<日期>-2.txt), 绝不覆盖旧作文
    - UTF-8 编码; 写后回读校验标题与字数; 输出最终文件路径

可选参数:
    --dir <目录>    指定保存目录(默认探测桌面)
    --dry-run       写到系统临时目录, 不碰真实桌面(用于验证)
    --date YYYY-MM-DD  指定日期(测试用)
"""
import argparse
import datetime
import os
import sys
import tempfile


def detect_desktop():
    """跨平台探测桌面路径。"""
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
    """同名文件自动加序号, 返回不存在的路径。"""
    candidate = os.path.join(directory, base_name)
    n = 2
    while os.path.exists(candidate):
        root, ext = os.path.splitext(base_name)
        candidate = os.path.join(directory, "{}-{}{}".format(root, n, ext))
        n += 1
    return candidate


def main():
    parser = argparse.ArgumentParser(description="保存作文到桌面记事本")
    parser.add_argument("--title", required=True, help="作文标题(必填)")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--content", help="作文全文(直接传)")
    src.add_argument("--file", help="作文全文所在的文本文件路径")
    parser.add_argument("--dir", default=None, help="保存目录(默认自动探测桌面)")
    parser.add_argument("--dry-run", action="store_true", help="写到临时目录用于验证")
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD(测试用)")
    args = parser.parse_args()

    if args.date:
        try:
            d = datetime.datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            sys.exit("日期格式错误, 应为 YYYY-MM-DD")
    else:
        d = datetime.datetime.now()
    date_str = d.strftime("%Y-%m-%d")

    if args.content is not None:
        body = args.content
    else:
        if not os.path.isfile(args.file):
            sys.exit("作文内容文件不存在: {}".format(args.file))
        with open(args.file, "r", encoding="utf-8-sig") as f:
            body = f.read()

    if args.dry_run:
        target_dir = tempfile.mkdtemp(prefix="essay-writer-dryrun-")
    elif args.dir:
        target_dir = args.dir
    else:
        target_dir = detect_desktop()
    os.makedirs(target_dir, exist_ok=True)

    base_name = "作文-{}.txt".format(date_str)
    file_path = unique_path(target_dir, base_name)

    header = "《{}》\n\n".format(args.title.strip())
    with open(file_path, "w", encoding="utf-8-sig", newline="\n") as f:
        f.write(header + body.strip() + "\n")

    # 回读校验
    with open(file_path, "r", encoding="utf-8-sig") as f:
        saved = f.read()
    if args.title.strip() not in saved:
        sys.exit("校验失败: 标题未出现在文件中")
    body_len = len(saved.replace("\n", "").replace(" ", ""))
    print("MODE:{}".format("DRY-RUN" if args.dry_run else "REAL"))
    print("FILE:{}".format(file_path))
    print("TITLE_IN_FILE:ok")
    print("BODY_LEN(含标点):{}".format(body_len))
    print("VERIFY:ok")


if __name__ == "__main__":
    main()
