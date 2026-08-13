# -*- coding: utf-8 -*-
"""线程安全的环形历史缓冲。"""
import threading
from collections import deque
from dataclasses import dataclass


@dataclass
class NotificationItem:
    title: str
    body: str
    priority: int
    category: str
    ts: float  # epoch 秒


class History:
    def __init__(self, maxlen: int = 200):
        self._lock = threading.Lock()
        self._buf: deque = deque(maxlen=maxlen)

    def resize(self, maxlen: int) -> None:
        with self._lock:
            self._buf = deque(self._buf, maxlen=maxlen)

    def add(self, item: NotificationItem) -> None:
        with self._lock:
            self._buf.append(item)

    def latest(self, n: int = 50):
        with self._lock:
            items = list(self._buf)
        return items[-n:][::-1]  # 最新在前
