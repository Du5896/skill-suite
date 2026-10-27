# -*- coding: utf-8 -*-
"""terminal-commander：后台静默终端执行器（普通 + 管理员）。

设计要点：
- 后台运行：所有 PowerShell 调用都隐藏窗口（CREATE_NO_WINDOW），绝不弹窗骚扰用户
- 指令防错：每条命令先做 PowerShell 语法解析校验，语法错误直接拒绝执行并返回错误位置
- 管理员权限：run-admin 触发 UAC 提权，用户只需点击一次"是"；命令经 base64 传输，绝无引号/转义错误
- 结果稳定：所有输出经 UTF-8 JSON 文件回传，中文不乱码

用法（Windows）：
  python terminal.py check "命令"           # 仅校验命令语法（不执行）
  python terminal.py run "命令"             # 普通命令，后台静默执行
  python terminal.py run-admin "命令"       # 管理员命令，触发 UAC（用户点"是"后执行）
  python terminal.py ping                   # 自检：环境是否可用
"""
import base64
import json
import os
import subprocess
import sys
import tempfile
import uuid

CREATE_NO_WINDOW = 0x08000000
RESULT_TIMEOUT = 300          # 单条命令最长执行时间（秒）
MAX_OUTPUT = 8000             # 返回给 AI 的输出最大字符数
POWERSHELL = os.environ.get("POWERSHELL_PATH", "powershell.exe")

HERE = os.path.dirname(os.path.abspath(__file__))
ADMIN_RUNNER = os.path.join(HERE, "admin_runner.ps1")

# 语法校验模板（英文 ASCII，避免编码问题；命令经 base64 传入）
CHECK_SCRIPT = r"""
param([string]$CmdB64,[string]$OutFile)
$ErrorActionPreference='Continue'
try{
  $cmd=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($CmdB64))
  $tokens=$null;$errs=$null
  [void][System.Management.Automation.Language.Parser]::ParseInput($cmd,[ref]$tokens,[ref]$errs)
  if($errs.Count -gt 0){[pscustomobject]@{ok=$false;errors=@($errs|ForEach-Object{$_.Message})}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8}
  else{[pscustomobject]@{ok=$true}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8}
}catch{[pscustomobject]@{ok=$false;errors=@($_.Exception.Message)}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8}
"""

# 普通命令执行模板
RUN_SCRIPT = r"""
param([string]$CmdB64,[string]$OutFile)
$ErrorActionPreference='Continue'
try{
  $cmd=[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($CmdB64))
  $out=Invoke-Expression $cmd 2>&1|Out-String
  $code=0
  if($LASTEXITCODE -ne $null){$code=$LASTEXITCODE}
  [pscustomobject]@{ok=$true;exit=$code;output=$out.Trim()}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8
}catch{[pscustomobject]@{ok=$false;exit=1;output=$_.Exception.Message}|ConvertTo-Json -Compress|Out-File -FilePath $OutFile -Encoding utf8}
"""

# UAC 提权启动器（写临时 ps1 执行；提权进程隐藏窗口）
# 用 EncodedCommand(base64) 传递内部命令，彻底规避路径空格/引号问题
# launcher 状态写 StatusFile（utf-8），规避 stdout 编码损耗
LAUNCHER_SCRIPT = r"""
param([string]$StatusFile)
$ErrorActionPreference='Stop'
try{
  $inner="& '__RUNNER__' -CmdB64 '__B64__' -OutFile '__OUTFILE__'"
  $enc=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
  Start-Process -FilePath 'powershell.exe' -Verb RunAs -Wait -WindowStyle Hidden -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand',$enc)
  'OK' | Out-File -FilePath $StatusFile -Encoding utf8
}catch{
  $msg=$_.Exception.Message
  if($msg -match 'cancel|denied|declined|0x4c7|0x4C7|取消|拒绝'){'CANCELLED'|Out-File -FilePath $StatusFile -Encoding utf8}
  else{('ERR: '+$msg)|Out-File -FilePath $StatusFile -Encoding utf8}
}
"""


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _temp_path(prefix):
    return os.path.join(tempfile.gettempdir(), "%s_%s" % (prefix, uuid.uuid4().hex[:10]))


def _read_json_file(path):
    try:
        # PowerShell 5.1 Out-File -Encoding utf8 会写 UTF-8 BOM，必须用 utf-8-sig 剥掉
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _run_ps_file(ps1_content, cmd_text, timeout=RESULT_TIMEOUT):
    """写临时 ps1 执行，命令经 base64 传入；返回进程对象。"""
    ps1_path = _temp_path("term_ps1")
    ps1_path += ".ps1"
    with open(ps1_path, "w", encoding="ascii") as f:
        f.write(ps1_content)
    out_file = _temp_path("term_out") + ".json"
    args = [POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", ps1_path, "-CmdB64", _b64(cmd_text), "-OutFile", out_file]
    try:
        subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=CREATE_NO_WINDOW,
                       timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "命令执行超时（超过 %d 秒），可能仍在后台运行" % timeout}
    finally:
        try:
            os.remove(ps1_path)
        except OSError:
            pass
    result = _read_json_file(out_file)
    if result is None:
        return {"ok": False, "error": "执行器无结果返回，请检查 PowerShell 是否可用"}
    return result


def _read_status_file(path):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except Exception:
        return ""
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def check(cmd_text):
    """仅校验命令语法。"""
    if not cmd_text.strip():
        return {"ok": False, "errors": ["命令为空"]}
    return _run_ps_file(CHECK_SCRIPT, cmd_text)


def run(cmd_text):
    """普通命令：先语法校验，通过后后台静默执行。"""
    chk = check(cmd_text)
    if not chk.get("ok"):
        return {"ok": False, "error": "命令语法有误，已拒绝执行（指令防错）",
                "errors": chk.get("errors")}
    result = _run_ps_file(RUN_SCRIPT, cmd_text)
    if result.get("ok") and len(result.get("output", "")) > MAX_OUTPUT:
        result["output"] = result["output"][:MAX_OUTPUT] + "\n…（输出过长已截断）"
    return result


def run_admin(cmd_text):
    """管理员命令：语法校验 → UAC 提权（用户点"是"）→ 静默执行。"""
    chk = check(cmd_text)
    if not chk.get("ok"):
        return {"ok": False, "error": "命令语法有误，已拒绝执行（指令防错）",
                "errors": chk.get("errors")}
    if not os.path.exists(ADMIN_RUNNER):
        return {"ok": False, "error": "缺少 admin_runner.ps1，无法执行管理员命令"}
    b64 = _b64(cmd_text)
    out_file = _temp_path("term_admin") + ".json"
    status_file = _temp_path("term_status") + ".txt"
    launcher = (LAUNCHER_SCRIPT
                .replace("__RUNNER__", ADMIN_RUNNER)
                .replace("__B64__", b64)
                .replace("__OUTFILE__", out_file))
    launcher_path = _temp_path("term_launch") + ".ps1"
    # launcher 含中文字符（取消匹配），用 utf-8-sig 带 BOM 写，PowerShell 5.1 才能正确解析
    with open(launcher_path, "w", encoding="utf-8-sig") as f:
        f.write(launcher)
    try:
        p = subprocess.run([POWERSHELL, "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", launcher_path, "-StatusFile", status_file],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", creationflags=CREATE_NO_WINDOW,
                           timeout=RESULT_TIMEOUT + 120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "管理员授权等待超时"}
    finally:
        try:
            os.remove(launcher_path)
        except OSError:
            pass
    status = _read_status_file(status_file)
    if status == "CANCELLED":
        return {"ok": False, "error": "用户取消了管理员授权，命令未执行"}
    if status.startswith("ERR:"):
        return {"ok": False, "error": status[4:].strip()}
    if status != "OK":
        return {"ok": False, "error": "管理员授权流程异常（%s）" % (status or "无状态")}
    result = _read_json_file(out_file)
    if result is None:
        return {"ok": False, "error": "提权执行无结果返回（可能授权被取消）"}
    if result.get("ok") and len(result.get("output", "")) > MAX_OUTPUT:
        result["output"] = result["output"][:MAX_OUTPUT] + "\n…（输出过长已截断）"
    return result


def self_test():
    out = []
    out.append("PowerShell: %s" % POWERSHELL)
    r1 = check("Get-Date")
    out.append("check(合法命令): %s" % json.dumps(r1, ensure_ascii=False))
    r2 = check("Get-Date")
    r2b = check("这是一条【明显语法错误!!!命令")
    out.append("check(非法命令): %s" % json.dumps(r2b, ensure_ascii=False))
    r3 = run("echo '后台静默测试-中文输出正常'")
    out.append("run(普通): %s" % json.dumps(r3, ensure_ascii=False))
    return "\n".join(out)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "ping":
        print(self_test())
        return
    if len(sys.argv) < 3:
        print(__doc__)
        return
    text = " ".join(sys.argv[2:])
    if cmd == "check":
        print(json.dumps(check(text), ensure_ascii=False, indent=2))
    elif cmd == "run":
        print(json.dumps(run(text), ensure_ascii=False, indent=2))
    elif cmd == "run-admin":
        print(json.dumps(run_admin(text), ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
