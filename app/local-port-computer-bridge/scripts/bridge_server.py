# -*- coding: utf-8 -*-
"""local-port-computer-bridge 本地桥接服务（零第三方依赖，仅标准库）。

启动：python bridge_server.py
监听：127.0.0.1:58201（仅本机回环，不开放外网）
指令格式：类别|动作|参数1|参数2
日志：bridge_log.txt（保存在脚本所在目录）

安全：
- 仅接受来自 127.0.0.1 的连接
- 删除文件 / 结束进程为高危操作，指令必须带 CONFIRMED: 标记，否则拒绝
"""
import socket
import subprocess
import os
import shutil
import base64
import datetime

HOST = "127.0.0.1"
PORT = 58201
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_log.txt")

HIGH_RISK = {"delete_file", "close"}  # 高危动作，必须带 CONFIRMED:


def write_log(text):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("%s  %s\n" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text))
    except Exception:
        pass


def ps_run(ps_text):
    """用 PowerShell 执行（中文安全：UTF-16LE base64 EncodedCommand）。"""
    try:
        b64 = base64.b64encode(ps_text.encode("utf-16-le")).decode("ascii")
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", b64],
            capture_output=True, timeout=30,
        )
        return (r.stdout or b"").decode("utf-8", "replace").strip()
    except Exception as e:
        return "PowerShell 调用失败：%s" % e


def execute_command(cmd_text):
    cmd_text = (cmd_text or "").strip()
    if not cmd_text:
        return "空指令"
    write_log("收到指令：%s" % cmd_text)
    parts = [p.strip() for p in cmd_text.split("|")]
    if len(parts) < 2:
        write_log("拒绝：格式错误")
        return "指令格式错误，应为 类别|动作|参数"
    category, action = parts[0].lower(), parts[1].lower()
    params = parts[2:]

    try:
        # ---- 高危检查：删除/结束进程必须带 CONFIRMED: ----
        if action in HIGH_RISK:
            confirmed = any(p.startswith("CONFIRMED:") for p in params)
            if not confirmed:
                write_log("拒绝高危操作（无确认标记）：%s" % cmd_text)
                return "高危操作被拒绝：指令缺少 CONFIRMED: 确认标记。请先向用户确认后再发带标记的指令。"

        if category == "file":
            if action == "create_folder":
                if not params:
                    return "缺少路径参数"
                os.makedirs(params[0], exist_ok=True)
                return "已创建文件夹：%s" % params[0]
            if action == "open":
                if not params:
                    return "缺少路径参数"
                os.startfile(params[0])
                return "已打开：%s" % params[0]
            if action == "copy":
                if len(params) < 2:
                    return "缺少源/目标参数"
                if os.path.isdir(params[0]):
                    shutil.copytree(params[0], params[1], dirs_exist_ok=True)
                else:
                    shutil.copy2(params[0], params[1])
                return "已复制：%s → %s" % (params[0], params[1])
            if action == "move":
                if len(params) < 2:
                    return "缺少源/目标参数"
                shutil.move(params[0], params[1])
                return "已移动：%s → %s" % (params[0], params[1])
            if action == "delete_file":
                target = next((p for p in params if not p.startswith("CONFIRMED:")), None)
                if not target:
                    return "缺少要删除的路径"
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=False)
                else:
                    os.remove(target)
                write_log("已执行删除：%s" % target)
                return "已删除：%s" % target
            return "未知文件动作：%s" % action

        if category == "app":
            if action == "run":
                if not params:
                    return "缺少程序参数"
                subprocess.Popen(params[0], shell=True)
                return "已启动：%s" % params[0]
            if action == "close":
                proc = next((p for p in params if not p.startswith("CONFIRMED:")), None)
                if not proc:
                    return "缺少进程名"
                subprocess.run(["taskkill", "/f", "/im", proc], capture_output=True, timeout=30)
                return "已结束进程：%s" % proc
            return "未知程序动作：%s" % action

        if category == "sys":
            if action == "msg":
                if not params:
                    return "缺少弹窗文字"
                ps_run("Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.MessageBox]::Show('%s','提示')" % params[0].replace("'", "''"))
                return "已弹窗提示"
            if action == "clipboard_write":
                if not params:
                    return "缺少剪贴板文本"
                ps_run("Set-Clipboard -Value '%s'" % params[0].replace("'", "''"))
                return "已写入剪贴板"
            return "未知系统动作：%s" % action

        return "未知指令类别：%s" % category
    except Exception as e:
        write_log("执行失败：%s" % e)
        return "执行失败：%s" % e


def start_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(1)
    write_log("桥接服务已启动，监听 %s:%d" % (HOST, PORT))
    print("桥接服务已启动，监听 %s:%d" % (HOST, PORT))
    print("按 Ctrl+C 停止。日志：%s" % LOG_FILE)
    while True:
        try:
            conn, addr = sock.accept()
            if addr[0] != "127.0.0.1":
                write_log("拒绝非本机连接：%s" % str(addr))
                conn.close()
                continue
            with conn:
                data = conn.recv(8192).decode("utf-8", "replace").strip()
                if data:
                    res = execute_command(data)
                    try:
                        conn.sendall(res.encode("utf-8"))
                    except Exception:
                        pass
        except KeyboardInterrupt:
            write_log("服务已停止")
            break
        except Exception as e:
            write_log("连接处理异常：%s" % e)


if __name__ == "__main__":
    start_server()
