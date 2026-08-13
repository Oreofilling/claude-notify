# -*- coding: utf-8 -*-
"""配置读写：%APPDATA%\\ClaudeNotify\\config.json（线程安全，深合并默认值）。"""
import json
import os
import threading
from dataclasses import dataclass, field, asdict

from .constants import DEFAULT_CONFIG, CONFIG_PATH, CATEGORIES

_LOCK = threading.Lock()


def _deep_merge(default: dict, override: dict) -> dict:
    out = dict(default)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _read_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # 原子替换


@dataclass
class Config:
    server_url: str = "https://ntfy.sh"
    topic: str = ""
    token: str = ""
    enabled: dict = field(default_factory=lambda: {c: True for c in CATEGORIES})
    sound_default: bool = True
    sound_urgent_loop: bool = True
    pause_all: bool = False
    autostart: bool = False
    history_size: int = 200

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls) -> "Config":
        with _LOCK:
            data = _deep_merge(DEFAULT_CONFIG, _read_json(CONFIG_PATH))
        c = cls()
        c.server_url = str(data.get("server_url", c.server_url))
        c.topic = str(data.get("topic", c.topic)).strip()
        c.token = str(data.get("token", c.token)).strip()
        c.enabled = {k: bool(data.get("enabled", {}).get(k, True)) for k in CATEGORIES}
        c.sound_default = bool(data.get("sound_default", True))
        c.sound_urgent_loop = bool(data.get("sound_urgent_loop", True))
        c.pause_all = bool(data.get("pause_all", False))
        c.autostart = bool(data.get("autostart", False))
        c.history_size = int(data.get("history_size", 200))
        return c

    def save(self) -> None:
        with _LOCK:
            _write_json(CONFIG_PATH, self.to_dict())
