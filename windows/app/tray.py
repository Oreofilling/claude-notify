# -*- coding: utf-8 -*-
"""系统托盘：pystray Icon/Menu/图标状态切换。

App 协调器(main.App)实现：test/show_history/show_settings/
toggle_pause/toggle_autostart/quit 以及 is_paused/is_autostart。
"""
import logging
import os

from PIL import Image, ImageDraw, ImageFont

try:
    import pystray
    from pystray import MenuItem, Menu
    _HAS_TRAY = True
except Exception as _e:
    logging.getLogger("claude-notify.tray").warning("pystray 不可用: %r", _e)
    _HAS_TRAY = False


def _font(size: int):
    """优先用系统粗体 TrueType，回退到 PIL 默认字体。"""
    for p in (r"C:\Windows\Fonts\arialbd.ttf",
              r"C:\Windows\Fonts\segoeuib.ttf",
              r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _make_image(letter: str, bg: str, fg="white") -> Image.Image:
    """圆角彩色方块 + 居中粗体大字母，更像真实 App 图标（非纯色方块）。
    高分辨率(128)绘制，pystray 缩放到托盘尺寸仍清晰。"""
    size = 128
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, size - 4, size - 4], radius=28, fill=bg)
    f = _font(86)
    try:
        bbox = d.textbbox((0, 0), letter, font=f)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
               letter, font=f, fill=fg)
    except Exception:
        d.rounded_rectangle([36, 36, size - 36, size - 36], radius=16, fill=fg)
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
