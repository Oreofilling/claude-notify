# -*- coding: utf-8 -*-
"""ntfy 流式订阅线程。

GET <url>/<topic>/json（long-poll），逐行解析；断线指数退避；
心跳看门狗：ntfy 每 ~30s 发 keepalive，>90s 无任何行即强制重连。
连接由本机主动发起 -> 天然穿透 NAT，无需开端口。
"""
import json
import logging
import threading
import time
import traceback

import requests

log = logging.getLogger("claude-notify.subscriber")

# tags 含 emoji + 类别词；提取类别词用于过滤
_KNOWN_CATEGORIES = ("stop", "idle", "permission", "other")

# 退避参数：错误越多间隔越长，避免 hammer ntfy 触发 429。
_BACKOFF_MIN = 2.0
_BACKOFF_MAX = 300.0
_BACKOFF_FACTOR = 2.0
# 429 专用：直接跳到较大间隔。
_BACKOFF_429 = 30.0


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
        self._guard = None  # 当前轮的 watchdog 协调 Event
        self._lock = threading.Lock()

    def stop(self) -> None:
        self._stop_evt.set()
        with self._lock:
            resp = self._resp
            guard = self._guard
        if guard is not None:
            try:
                guard.set()
            except Exception:
                pass
        try:
            if resp is not None:
                resp.close()
        except Exception:
            pass

    def run(self) -> None:
        backoff = _BACKOFF_MIN
        while not self._stop_evt.is_set():
            ok = False
            try:
                self._on_status("connecting")
                resp = requests.get(
                    self._stream_url(),
                    stream=True,
                    headers=self._headers(),
                    timeout=(10, 90),
                )
                resp.raise_for_status()
                with self._lock:
                    self._resp = resp
                    # 每轮新建一个 guard，旧 guard 置位后旧 watchdog 自然退出。
                    if self._guard is not None:
                        try:
                            self._guard.set()
                        except Exception:
                            pass
                    self._guard = threading.Event()
                    guard = self._guard
                self._on_status("connected")
                # 成功建连后重置退避（但保留最小值），交给心跳看门狗。
                backoff = _BACKOFF_MIN
                last_line_ts = [time.monotonic()]
                threading.Thread(
                    target=self._watchdog,
                    args=(resp, last_line_ts, guard),
                    daemon=True,
                ).start()
                for line in resp.iter_lines(decode_unicode=True):
                    if self._stop_evt.is_set():
                        break
                    last_line_ts[0] = time.monotonic()
                    if not line:
                        continue  # keepalive 空行
                    self._on_line(line)
                ok = True
            except Exception as e:
                if self._stop_evt.is_set():
                    break
                # 完整 traceback，便于定位偶发错误（如历史 _ThreadHandle TypeError）。
                log.warning("subscribe error: %s\n%s", repr(e), traceback.format_exc())
                self._on_status("reconnecting")
                # 429 / 其它限流直接跳到较大退避。
                if _is_rate_limited(e):
                    backoff = max(backoff, _BACKOFF_429)
                    log.warning("被限流(429)，%ss 后重试", int(backoff))
            finally:
                with self._lock:
                    resp = self._resp
                    guard = self._guard
                    self._resp = None
                if guard is not None:
                    try:
                        guard.set()
                    except Exception:
                        pass
                try:
                    if resp is not None:
                        resp.close()
                except Exception:
                    pass
            if self._stop_evt.is_set():
                break
            if ok:
                # 正常流结束（服务器关流）也按退避重连。
                backoff = _BACKOFF_MIN
            time.sleep(backoff)
            backoff = min(backoff * _BACKOFF_FACTOR, _BACKOFF_MAX)

    def _stream_url(self) -> str:
        base = (self._cfg.server_url or "https://ntfy.sh").rstrip("/")
        # since=1s：首次只取近 1 秒，避免回放历史噪音
        return "%s/%s/json?since=1s" % (base, self._cfg.topic)

    def _headers(self) -> dict:
        h = {}
        if self._cfg.token:
            h["Authorization"] = "Bearer " + self._cfg.token
        return h

    def _watchdog(self, resp, last_line_ts, guard) -> None:
        """守护某一轮的具体 resp。guard 被置位即本轮结束，退出。"""
        while not self._stop_evt.is_set():
            if guard.is_set():
                return
            time.sleep(15)
            if self._stop_evt.is_set() or guard.is_set():
                return
            if time.monotonic() - last_line_ts[0] > 90:
                log.warning("watchdog: 无数据 >90s，强制重连")
                try:
                    resp.close()
                except Exception:
                    pass
                return

    # 注意：方法名不能叫 _handle —— Python 3.13 的 threading.Thread.__init__
    # 会设置实例属性 self._handle（_thread._ThreadHandle），会覆盖同名方法，
    # 导致 self._handle(line) 报 "_thread._ThreadHandle object is not callable"。
    def _on_line(self, line: str) -> None:
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


def _is_rate_limited(e: BaseException) -> bool:
    """识别 ntfy.sh 429 限流（requests 的 HTTPError，状态码 429）。"""
    if isinstance(e, requests.HTTPError):
        resp = getattr(e, "response", None)
        if resp is not None and resp.status_code == 429:
            return True
    return getattr(e, "status_code", None) == 429
