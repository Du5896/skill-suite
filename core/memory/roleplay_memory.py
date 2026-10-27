# -*- coding: utf-8 -*-
"""agent-roleplay 全量记忆系统：用户说过的话，什么都记得住。

设计核心：全量追加、永不裁剪。quotes（用户原话）/ events（剧情事件）/
summary（剧情摘要）不设条数上限；character / user / prefs 逐条累积，
相同内容去重防重复写入。记忆文件存在桌面 roleplay-memory.json。

用法（Windows 建议用 python 解释器直接执行）：
  python memory.py character 小精灵，住在手机屏幕里，活泼粘人
  python memory.py user 用户是男生，喜欢被叫主人
  python memory.py pref 用户不喜欢血腥剧情
  python memory.py quote 明天带我去花园玩
  python memory.py log 小精灵给主人表演了会飞的萤火虫
  python memory.py load            # 输出全部记忆（AI 跨会话恢复用）
  python memory.py recall 花园     # 按关键词检索记忆
  python memory.py clear           # 清空全部记忆（换新角色时用）
"""
import json
import os
import sys
import datetime

# 各字段用途：全量保留，不裁剪
DEFAULT_STATE = {
    "character": [],   # 角色设定（身份/性格/背景/口癖……）逐条累积
    "user": [],        # 用户信息（用户说过关于自己的话）逐条累积
    "prefs": [],       # 约定 / 偏好（用户要求记住的规则）逐条累积
    "quotes": [],      # 用户原话（每轮原样全记，永不删除）
    "events": [],      # 剧情事件（每次重要剧情全量追加，永不删除）
    "summary": [],     # 剧情摘要（每轮结尾 AI 写的一句总结，全量保留）
    "updated": "",
}


def desktop_dir():
    if os.name == "nt":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    return os.path.join(os.path.expanduser("~"), "Desktop")


def state_path():
    return os.path.join(desktop_dir(), "roleplay-memory.json")


def load_state():
    try:
        with open(state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_STATE)
        for k, v in data.items():
            if k in merged and isinstance(v, list):
                merged[k] = v
        return merged
    except Exception:
        return dict(DEFAULT_STATE)


def save_state(state):
    state["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(state_path(), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("SAVED:", state_path())


def add_dedup(items, text):
    """追加条目；完全相同的内容不重复（防 AI 重复写入同一条）。"""
    text = text.strip()
    if not text:
        return
    if text not in items:
        items.append(text)


def add_always(items, text):
    """原样全记，不裁剪不去重（用于用户原话）。"""
    text = text.strip()
    if text:
        items.append(text)


def cmd_add(state, field, text):
    add_dedup(state[field], text)
    save_state(state)
    print("OK [%s] %d 条" % (field, len(state[field])))


def cmd_quote(state, text):
    add_always(state["quotes"], text)
    save_state(state)
    print("OK [quotes] %d 条" % len(state["quotes"]))


def cmd_load(state):
    out = []
    out.append("=== 角色设定 character ===")
    out += state["character"] or ["（无）"]
    out.append("=== 用户信息 user ===")
    out += state["user"] or ["（无）"]
    out.append("=== 约定/偏好 prefs ===")
    out += state["prefs"] or ["（无）"]
    out.append("=== 用户原话 quotes（共 %d 条，全量）===" % len(state["quotes"]))
    out += state["quotes"] or ["（暂无）"]
    out.append("=== 剧情事件 events（共 %d 条，全量）===" % len(state["events"]))
    out += state["events"] or ["（暂无）"]
    out.append("=== 剧情摘要 summary（共 %d 条）===" % len(state["summary"]))
    out += state["summary"] or ["（暂无）"]
    print("\n".join(out))


def cmd_recall(state, keyword):
    hits = []
    for field in ("character", "user", "prefs", "quotes", "events", "summary"):
        for item in state[field]:
            if keyword in item:
                hits.append("[%s] %s" % (field, item))
    if hits:
        print("命中 %d 条：\n" % len(hits) + "\n".join(hits))
    else:
        print("未找到与「%s」相关的记忆" % keyword)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    state = load_state()

    if cmd == "clear":
        save_state(dict(DEFAULT_STATE))
        print("CLEARED：记忆已清空（换新角色时使用）")
        return
    if cmd == "load":
        cmd_load(state)
        return
    if len(sys.argv) < 3:
        print(__doc__)
        return
    text = " ".join(sys.argv[2:]).strip()

    if cmd == "character":
        cmd_add(state, "character", text)
    elif cmd == "user":
        cmd_add(state, "user", text)
    elif cmd == "pref":
        cmd_add(state, "prefs", text)
    elif cmd == "quote":
        cmd_quote(state, text)
    elif cmd == "log":
        stamp = datetime.datetime.now().strftime("%m-%d %H:%M")
        add_dedup(state["events"], "%s %s" % (stamp, text))
        save_state(state)
        print("OK [events] %d 条" % len(state["events"]))
    elif cmd == "summary":
        add_dedup(state["summary"], text)
        save_state(state)
        print("OK [summary] %d 条" % len(state["summary"]))
    elif cmd == "recall":
        cmd_recall(state, text)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
