# -*- coding: utf-8 -*-
"""系统托盘：pystray Icon/Menu/图标状态切换。

App 协调器(main.App)实现：test/show_history/show_settings/
toggle_pause/toggle_autostart/quit 以及 is_paused/is_autostart。
"""
import logging

from PIL import Image, ImageDraw

try:
    import pystray
    from pystray import MenuItem, Menu
    _HAS_TRAY = True
except Exception as _e:
    logging.getLogger("claude-notify.tray").warning("pystray 不可用: %r", _e)
    _HAS_TRAY = False


def _make_image(letter: str, bg: str, fg="white") -> Image.Image:
    img = Image.new("RGB", (64, 64), bg)
    d = ImageDraw.Draw(img)
    try:
        d.text((20, 16), letter, fill=fg)
    except Exception:
        d.rectangle([22, 22, 42, 42], fill=fg)
    return img


def _images() -> dict:
    return {
        "idle": _make_image("C", "#3b82f6"),
        "unread": _make_image("C", "#f59e0b"),
        "error": _make_image("!", "#ef4444"),
    }


_TIP = {"idle": "Claude Notify · 已连接", "unread": "Claude Notify · 有新通知",
        "error": "Claude Notify · 连接断开，重连中…"}


class Tray:
    """pystray 在主线程 run()；tkinter 对话框由 App 在新线程跑。"""

    def __init__(self, app):
        self._app = app
        self._state = "idle"
        self._icons = _images()
        if not _HAS_TRAY:
            return
        self._icon = pystray.Icon(
            "ClaudeNotify", self._icons["idle"], _TIP["idle"], self._menu()
        )

    def _menu(self):
        app = self._app
        return Menu(
            MenuItem("Claude Notify", None, enabled=False),
            Menu.SEPARATOR,
            MenuItem("发送测试通知", lambda: app.test()),
            MenuItem("历史记录", lambda: app.show_history()),
            MenuItem("设置…", lambda: app.show_settings()),
            Menu.SEPARATOR,
            MenuItem("暂停全部通知", app.toggle_pause,
                     checked=lambda _i: app.is_paused()),
            MenuItem("开机自启", app.toggle_autostart,
                     checked=lambda _i: app.is_autostart()),
            Menu.SEPARATOR,
            MenuItem("退出", app.quit),
        )

    def run(self) -> None:
        if not _HAS_TRAY:
            logging.getLogger("claude-notify.tray").error("无托盘后端，主线程空转")
            import threading, time
            while True:
                time.sleep(3600)
        self._icon.run()

    def stop(self) -> None:
        if _HAS_TRAY:
            try:
                self._icon.stop()
            except Exception:
                pass

    def set_state(self, state: str) -> None:
        self._state = state
        if not _HAS_TRAY:
            return
        img = self._icons.get(state) or self._icons["idle"]
        try:
            self._icon.icon = img
            self._icon.title = _TIP.get(state, _TIP["idle"])
        except Exception:
            pass
