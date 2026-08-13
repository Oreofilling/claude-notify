#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ClaudeNotify 入口：装配 config + subscriber + tray 并运行。

pystray 在主线程 run()；订阅器/对话框为 daemon 线程。
首次无 topic 时立即弹设置框（仍同时显示托盘）。
"""
import logging
import os
import threading
import time
from logging.handlers import RotatingFileHandler

from app.config import Config
from app.constants import LOG_PATH, appdata_dir
from app.history import History, NotificationItem
from app.subscriber import NtfySubscriber
from app.notifier import show as show_toast
from app.tray import Tray
from app import autostart


def _setup_logging() -> None:
    """控制台 + 滚动文件双输出。

    文件始终写到 %APPDATA%\\ClaudeNotify\\app.log，便于排障——
    这样即使经 pythonw（无 stdout）启动也有日志可查。
    """
    os.makedirs(appdata_dir(), exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)


_setup_logging()
log = logging.getLogger("claude-notify")


class App:
    def __init__(self):
        self.config = Config.load()
        self.history = History(self.config.history_size)
        self.tray = Tray(self)
        self.subscriber = None

    # ---- 订阅器生命周期 ----
    def start_subscriber(self):
        if not self.config.topic:
            log.info("无 topic，跳过订阅（等待设置）")
            return
        self.subscriber = NtfySubscriber(self.config, self.on_message, self.on_status)
        self.subscriber.start()

    def restart_subscriber(self):
        if self.subscriber:
            self.subscriber.stop()
        self.start_subscriber()

    # ---- 订阅器回调 ----
    def on_message(self, item: dict):
        cat = item.get("category", "other")
        if not self.config.enabled.get(cat, True):
            log.info("类别 %s 已禁用，跳过", cat)
            return
        ni = NotificationItem(
            title=item["title"], body=item["body"],
            priority=item["priority"], category=cat, ts=time.time(),
        )
        self.history.add(ni)
        log.info("收到通知: %s | prio=%s | cat=%s", ni.title, ni.priority, cat)
        show_toast(ni.title, ni.body, ni.priority, self.config, cat)
        self.tray.set_state("unread")

    def on_status(self, status: str):
        log.info("订阅状态: %s", status)
        if status == "connected":
            self.tray.set_state("idle")
        elif status in ("connecting", "reconnecting"):
            self.tray.set_state("error")

    # ---- 托盘菜单动作 ----
    def is_paused(self) -> bool:
        return self.config.pause_all

    def is_autostart(self) -> bool:
        return self.config.autostart

    def toggle_pause(self):
        self.config.pause_all = not self.config.pause_all
        self.config.save()

    def toggle_autostart(self):
        self.config.autostart = not self.config.autostart
        self.config.save()
        autostart.set_enabled(self.config.autostart)

    def test(self):
        threading.Thread(
            target=lambda: show_toast("Claude 测试通知", "通知链路正常 ✅（本地直接弹出）", 3, self.config, "stop"),
            daemon=True,
        ).start()

    def show_settings(self):
        from app.settings_dialog import SettingsDialog

        def _run():
            SettingsDialog(self.config, self.on_config_saved).show()
        threading.Thread(target=_run, daemon=True).start()

    def show_history(self):
        from app.history_dialog import show_history as _show

        def _run():
            _show(self.history)
        threading.Thread(target=_run, daemon=True).start()

    def on_config_saved(self, new_cfg: Config):
        self.config = new_cfg
        self.history.resize(new_cfg.history_size)
        self.restart_subscriber()

    def quit(self):
        log.info("退出中…")
        if self.subscriber:
            self.subscriber.stop()
        self.tray.stop()


def main():
    app = App()

    if not app.config.topic:
        from app.settings_dialog import SettingsDialog

        def _first_run():
            SettingsDialog(app.config, app.on_config_saved).show()
        threading.Thread(target=_first_run, daemon=True).start()
    else:
        app.start_subscriber()

    app.tray.run()  # 阻塞主线程


if __name__ == "__main__":
    main()
