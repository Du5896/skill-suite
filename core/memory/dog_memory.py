# -*- coding: utf-8 -*-
"""dog-sim 全量记忆系统：主人说过的话、小可经历的事，什么都记得住。

设计核心：全量追加、永不裁剪。quotes（主人原话）/ events（剧情事件）/
summary（剧情摘要）不设条数上限；xiaoke / user / prefs 逐条累积，
相同内容去重防重复写入；state 是当前状态卡（场景/在做什么/健康/心情，覆盖式）。
记忆文件存在桌面 dog-memory.json（与 agent-roleplay 的 roleplay-memory.json 相互独立）。

用法（Windows 建议用 python 解释器直接执行）：
  python memory.py xiaoke 小可档案：可卡布，活泼黏人，健康
  python memory.py user 主人是男性，非常有钱，华为全家桶
  python memory.py pref 小可平时和主人一起睡
  python memory.py quote 明天带小可去玩具店买皮球
  python memory.py log 小可在玩具店挑中一颗印爪印的皮球
  python memory.py summary 主人带小可去玩具店买了一颗皮球
  python memory.py state 场景:玩具店|在做什么:挑玩具|健康:健康|心情:兴奋
  python memory.py load            # 输出全部记忆（AI 跨会话恢复用）
  python memory.py recall 皮球     # 按关键词检索记忆
  python memory.py clear           # 清空全部记忆（重新开始养时用）
"""
import json
import os
import sys
import datetime

DEFAULT_STATE = {
    "xiaoke": [],      # 小可档案（名字/品种/性格/健康/心情变化）逐条累积
    "user": [],        # 主人信息（用户说过关于自己的话）逐条累积
    "prefs": [],       # 约定 / 偏好（用户要求记住的规则）逐条累积
    "quotes": [],      # 主人原话（每轮原样全记，永不删除）
    "events": [],      # 剧情事件（每次重要剧情全量追加，永不删除）
    "summary": [],     # 剧情摘要（每轮结尾 AI 写的一句总结，全量保留）
    "state": {},       # 当前状态卡（场景/在做什么/健康/心情，覆盖式）
    "updated": "",
}


def desktop_dir():
    if os.name == "nt":
        return os.path.join(os.environ.get("USERPROFILE", ""), "Desktop")
    return os.path.join(os.path.expanduser("~"), "Desktop")


def state_path():
    return os.path.join(desktop_dir(), "dog-memory.json")


def load_state():
    try:
        with open(state_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(DEFAULT_STATE)
        for k, v in data.items():
            if k in merged and isinstance(v, (list, dict)):
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
    """原样全记，不裁剪不去重（用于主人原话）。"""
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


def cmd_state(state, text):
    """解析 'k:v|k:v|...' 写入状态卡（覆盖式）。"""
    for part in text.split("|"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            state["state"][k] = v
    save_state(state)
    print("OK [state]", json.dumps(state["state"], ensure_ascii=False))


def cmd_load(state):
    out = []
    out.append("=== 当前状态卡 state ===")
    out.append(json.dumps(state["state"], ensure_ascii=False) if state["state"] else "（空）")
    out.append("=== 小可档案 xiaoke ===")
    out += state["xiaoke"] or ["（无）"]
    out.append("=== 主人信息 user ===")
    out += state["user"] or ["（无）"]
    out.append("=== 约定/偏好 prefs ===")
    out += state["prefs"] or ["（无）"]
    out.append("=== 主人原话 quotes（共 %d 条，全量）===" % len(state["quotes"]))
    out += state["quotes"] or ["（暂无）"]
    out.append("=== 剧情事件 events（共 %d 条，全量）===" % len(state["events"]))
    out += state["events"] or ["（暂无）"]
    out.append("=== 剧情摘要 summary（共 %d 条）===" % len(state["summary"]))
    out += state["summary"] or ["（暂无）"]
    print("\n".join(out))


def cmd_recall(state, keyword):
    hits = []
    for field in ("xiaoke", "user", "prefs", "quotes", "events", "summary"):
        for item in state[field]:
            if keyword in item:
                hits.append("[%s] %s" % (field, item))
    for k, v in state["state"].items():
        if keyword in k or keyword in v:
            hits.append("[state] %s:%s" % (k, v))
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
        print("CLEARED：记忆已清空（重新开始养时使用）")
        return
    if cmd == "load":
        cmd_load(state)
        return
    if len(sys.argv) < 3:
        print(__doc__)
        return
    text = " ".join(sys.argv[2:]).strip()

    if cmd == "xiaoke":
        cmd_add(state, "xiaoke", text)
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
    elif cmd == "state":
        cmd_state(state, text)
    elif cmd == "recall":
        cmd_recall(state, text)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
