# -*- coding: utf-8 -*-
"""弹窗渲染：经【非打包】 powershell.exe 进程渲染 WinForms 弹窗(toast.ps1)。

为什么不用 win11toast 直接发：本机 Python 是 Microsoft Store 版(打包 / AppContainer
进程)，Win10 上打包进程不能以任意/未注册 AUMID 发 toast，平台一律返回 0x80380114。
改由 powershell.exe(非打包进程) 代发，绕开进程身份限制。

为什么用弹窗而非 toast 横幅：本机系统级抑制 toast 横幅(到通知中心但不弹出)，
WinForms TopMost 弹窗走窗口子系统，不受该抑制。

fire-and-forget(subprocess.Popen，不 wait)，绝不阻塞订阅器 / Claude 主链路。
category(stop/idle/permission/other) 决定弹窗的色条/图标/音效；slot 用于多条堆叠。
"""
import logging
import os
import subprocess
import threading
import time

from .constants import PRIO_URGENT

log = logging.getLogger("claude-notify.notifier")

# toast.ps1 与本文件同层再上一级(F:\claude-notify\toast.ps1)。
_PS1 = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "toast.ps1"))
_POWERSHELL = os.path.join(
    os.environ.get("SystemRoot", r"C:\Windows"),
    "System32", "WindowsPowerShell", "v1.0", "powershell.exe",
)
_CREATE_NO_WINDOW = 0x08000000

# 近期弹窗时间戳：8s 窗口内视为同时在屏，用于多条垂直堆叠互不遮挡。
_slot_lock = threading.Lock()
_shown: list = []


def _next_slot() -> int:
    now = time.time()
    with _slot_lock:
        _shown[:] = [t for t in _shown if now - t < 8.0]
        _shown.append(now)
        return len(_shown) - 1


def show(title: str, body: str, priority: int = 3, config=None,
         category: str = "other") -> None:
    """渲染一条弹窗。category 向后兼容(默认 other)；main.py 传入真实类别。"""
    cfg = config
    if cfg is not None and cfg.pause_all:
        log.info("pause_all=on，跳过: %s", title)
        return

    urgent = priority >= PRIO_URGENT
    silent = bool(cfg is not None and not cfg.sound_default)

    # category 决定色条/图标/音效；未给而 urgent 则视为 permission
    cat = category or ("permission" if urgent else "other")
    slot = _next_slot()

    extra = []
    if urgent:
        extra += ["-Scenario", "alarm"]
    elif silent:
        extra += ["-Silent", "1"]
    extra += ["-Category", cat, "-Slot", str(slot)]

    # subprocess 在 Windows 经 CreateProcessW 传宽字符，中文 title/body 不会乱码。
    cmd = [
        _POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
        "-File", _PS1, "-Title", title, "-Body", body,
    ] + extra

    try:
        subprocess.Popen(
            cmd, creationflags=_CREATE_NO_WINDOW, close_fds=True,
        )
        log.info("[popup-ok] cat=%s prio=%s slot=%s | %s", cat, priority, slot, title)
    except Exception as e:
        # 永不抛出影响主链路：仅记录
        log.warning("[popup-fail] 发起 powershell 失败: %r | prio=%s | %s", e, priority, title)
