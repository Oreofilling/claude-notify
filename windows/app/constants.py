# -*- coding: utf-8 -*-
"""常量与默认配置。

实际的 title/tags/priority 由服务器端钩子(claude_notify_hook.py)设置；
Windows 端只负责：按 priority 分级显示、按 tag 中的类别词(stop/idle/permission/other)过滤。
"""
import os

APP_NAME = "ClaudeNotify"
APP_ID = "ClaudeNotify.App"  # Windows Toast AppUserModelID

# ntfy 数值优先级（由服务器设置）
PRIO_URGENT = 5   # permission_prompt -> 常驻 + 循环报警
PRIO_HIGH = 4     # idle_prompt       -> 默认通知音
PRIO_DEFAULT = 3  # stop / other      -> 标准

# 类别词（与服务器 tags 中的第二个元素一一对应）
CATEGORIES = ("stop", "idle", "permission", "other")

DEFAULT_CONFIG = {
    "server_url": "https://ntfy.sh",
    "topic": "",
    "token": "",
    "enabled": {"stop": True, "idle": True, "permission": True, "other": True},
    "sound_default": True,
    "sound_urgent_loop": True,
    "pause_all": False,
    "autostart": False,
    "history_size": 200,
}


def appdata_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "ClaudeNotify")


CONFIG_PATH = os.path.join(appdata_dir(), "config.json")
LOG_PATH = os.path.join(appdata_dir(), "app.log")
