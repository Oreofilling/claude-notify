# -*- coding: utf-8 -*-
"""win11toast 封装：按 priority 分级显示。

urgent(5)：scenario=alarm 常驻 + 循环报警声（最该提醒的「请求授权」）
high(4)  ：默认通知音
default(3)及以下：标准
受 config.pause_all / sound_* 约束。
"""
import logging

from .constants import PRIO_URGENT, PRIO_HIGH

log = logging.getLogger("claude-notify.notifier")

try:
    from win11toast import toast as _toast
    _HAS_TOAST = True
except Exception as _e:  # 非 Windows 环境或库缺失
    log.warning("win11toast 不可用（将仅打印日志）: %r", _e)
    _HAS_TOAST = False


def show(title: str, body: str, priority: int = 3, config=None) -> None:
    cfg = config
    if cfg is not None and cfg.pause_all:
        log.info("pause_all=on，跳过: %s", title)
        return

    if not _HAS_TOAST:
        log.info("[no-toast] prio=%s | %s | %s", priority, title, body)
        return

    silent = bool(cfg is not None and not cfg.sound_default)
    audio = {"silent": silent}

    kwargs = {}
    if priority >= PRIO_URGENT:
        kwargs["scenario"] = "alarm"  # 常驻直到处理
        if cfg is not None and cfg.sound_urgent_loop:
            audio = {"silent": False, "loop": True,
                     "src": "ms-winsoundevent:Notification.Looping.Alarm"}
    elif priority >= PRIO_HIGH:
        pass  # 默认通知音
    kwargs["audio"] = audio

    try:
        _toast(title, body, **kwargs)
    except Exception as e:
        log.exception("toast failed: %r", e)
        log.info("[toast-fallback] prio=%s | %s | %s", priority, title, body)
