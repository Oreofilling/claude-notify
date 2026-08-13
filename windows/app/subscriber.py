# -*- coding: utf-8 -*-
"""ntfy 流式订阅线程。

GET <url>/<topic>/json（long-poll），逐行解析；断线指数退避 1->60s；
心跳看门狗：ntfy 每 ~30s 发 keepalive，>90s 无任何行即强制重连。
连接由本机主动发起 -> 天然穿透 NAT，无需开端口。
"""
import json
import logging
import threading
import time

import requests

log = logging.getLogger("claude-notify.subscriber")

# tags 含 emoji + 类别词；提取类别词用于过滤
_KNOWN_CATEGORIES = ("stop", "idle", "permission", "other")


def category_from_tags(tags) -> str:
    for t in tags or []:
        if t in _KNOWN_CATEGORIES:
            return t
    return "other"


class NtfySubscriber(threading.Thread):
    def __init__(self, config, on_message, on_status):
        super().__init__(daemon=True, name="ntfy-subscriber")
        self._cfg = config
        self._on_message = on_message  # callable(item: dict)
        self._on_status = on_status    # callable(status: str)
        self._stop_evt = threading.Event()
        self._resp = None
        self._last_line_ts = 0.0
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop_evt.set()
        with self._lock:
            resp = self._resp
        try:
            if resp is not None:
                resp.close()
        except Exception:
            pass

    def run(self) -> None:
        backoff = 1
        while not self._stop_evt.is_set():
            try:
                self._on_status("connecting")
                with self._lock:
                    self._resp = requests.get(
                        self._stream_url(),
                        stream=True,
                        headers=self._headers(),
                        timeout=(10, 90),
                    )
                    self._resp.raise_for_status()
                    resp = self._resp
                self._on_status("connected")
                backoff = 1
                self._last_line_ts = time.monotonic()
                threading.Thread(target=self._watchdog, daemon=True).start()
                for line in resp.iter_lines(decode_unicode=True):
                    if self._stop_evt.is_set():
                        break
                    self._last_line_ts = time.monotonic()
                    if not line:
                        continue  # keepalive 空行
                    self._handle(line)
            except Exception as e:
                if not self._stop_evt.is_set():
                    log.warning("subscribe error: %r", e)
                    self._on_status("reconnecting")
            finally:
                with self._lock:
                    resp = self._resp
                    self._resp = None
                try:
                    if resp is not None:
                        resp.close()
                except Exception:
                    pass
            if self._stop_evt.is_set():
                break
            time.sleep(backoff)
            backoff = min(backoff * 2, 60)

    def _stream_url(self) -> str:
        base = (self._cfg.server_url or "https://ntfy.sh").rstrip("/")
        # since=1s：首次只取近 1 秒，避免回放历史噪音
        return "%s/%s/json?since=1s" % (base, self._cfg.topic)

    def _headers(self) -> dict:
        h = {}
        if self._cfg.token:
            h["Authorization"] = "Bearer " + self._cfg.token
        return h

    def _watchdog(self) -> None:
        while not self._stop_evt.is_set():
            time.sleep(15)
            if self._stop_evt.is_set():
                break
            with self._lock:
                resp = self._resp
            if resp is None:
                break
            if time.monotonic() - self._last_line_ts > 90:
                log.warning("watchdog: 无数据 >90s，强制重连")
                try:
                    resp.close()
                except Exception:
                    pass
                break

    def _handle(self, line: str) -> None:
        try:
            m = json.loads(line)
        except Exception:
            return
        if m.get("event") != "message":
            return
        item = {
            "title": m.get("title") or "Claude 通知",
            "body": m.get("message") or "",
            "priority": int(m.get("priority") or 3),
            "category": category_from_tags(m.get("tags")),
        }
        try:
            self._on_message(item)
        except Exception as e:
            log.exception("on_message failed: %r", e)
