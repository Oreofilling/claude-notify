#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Code -> ntfy 通知桥（零第三方依赖，仅用标准库）。

作为 Claude Code 的 `Stop` / `Notification` 钩子运行：
  1. 从 stdin 读取钩子 JSON（{hook_event_name, notification_type, cwd, message, ...}）
  2. 按事件类型分类 -> 中文标题 + emoji/类别 tag + ntfy 优先级
  3. 用 urllib POST 到 ntfy topic

设计原则：
  - 永不抛出未捕获异常，绝不影响 Claude 会话；任何错误静默（可设 CLAUDE_NTFY_DEBUG=1 打到 stderr）。
  - 固定 5s 超时，避免拖慢 Claude。
  - 通知正文只含「项目名 + 文案」，绝不包含代码 / 命令行 / 文件路径 / 密钥。
"""
import sys
import os
import json
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.config/claude-notify/config.json")
DEFAULT_URL = "https://ntfy.sh"
TIMEOUT = 5  # 秒


def log(msg):
    """调试输出到 stderr（不影响 Claude，进程始终 exit 0）。"""
    if os.environ.get("CLAUDE_NTFY_DEBUG"):
        try:
            sys.stderr.write("[claude-notify] " + str(msg) + "\n")
            sys.stderr.flush()
        except Exception:
            pass


def load_config():
    """读取 ~/.config/claude-notify/config.json，失败则回退环境变量。"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict):
                return cfg
        except Exception as e:
            log("config read failed: %r" % e)
    return {
        "url": os.environ.get("CLAUDE_NTFY_URL", DEFAULT_URL),
        "topic": os.environ.get("CLAUDE_NTFY_TOPIC", ""),
        "token": os.environ.get("CLAUDE_NTFY_TOKEN", ""),
    }


def classify(data):
    """返回 (title, tags, priority, body)。

    tags 同时含 emoji 与类别词（stop/idle/permission/other），
    便于 Windows 端按类别词过滤；emoji 仅美化。
    ntfy priority: default | high | urgent（数值 3/4/5）。
    """
    hook = (data.get("hook_event_name") or "").strip()
    ntype = (data.get("notification_type") or "").strip()
    msg = data.get("message") or ""

    if hook == "Stop":
        return ("Claude 任务完成", "✅,stop", "default",
                msg or "已完成响应，等待你的下一步指令。")
    if ntype == "permission_prompt":
        # 任务被卡住直到用户批准，最该提醒 -> 最高优先级
        return ("Claude 请求授权", "\U0001F6A8,permission", "urgent",
                msg or "需要你批准工具权限才能继续，任务已暂停。")
    if ntype == "idle_prompt":
        return ("Claude 等待输入", "\U0001F4AC,idle", "high",
                msg or "Claude 在等你输入下一步。")
    # 兜底：auth_success / elicitation_* / agent_* 等已知或未知类型
    label = ntype or hook or "通知"
    return ("Claude 通知", "\U0001F514,other", "default",
            msg or ("事件: %s" % label))


# ntfy 数值优先级（JSON 发布接口用数字 1-5）
_PRIO = {"min": 1, "low": 2, "default": 3, "high": 4, "urgent": 5}


def _prio_num(p):
    return _PRIO.get(p, 3)


def build_body(base_body, data):
    """正文加项目名前缀（仅目录名，不含完整路径）。"""
    cwd = data.get("cwd") or ""
    proj = os.path.basename(cwd.rstrip("/")) if cwd else ""
    return ("[%s] %s" % (proj, base_body)) if proj else base_body


def publish(cfg, title, tags, priority, body):
    """用 ntfy JSON 发布接口 POST（标题/正文/标签含 UTF-8，header 方式会 latin-1 报错）。"""
    topic = (cfg.get("topic") or "").strip()
    if not topic:
        log("no topic configured; skip")
        return
    base = (cfg.get("url") or DEFAULT_URL).rstrip("/")
    url = base + "/"  # ntfy JSON 发布接口：POST 到根路径，topic 放在 body（POST /<topic> 会把 body 当纯文本）
    payload = {
        "topic": topic,
        "title": title,
        "message": body,
        "tags": [t for t in tags.split(",") if t],
        "priority": _prio_num(priority),
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json; charset=utf-8")
    token = cfg.get("token") or ""
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        resp.read()


def main():
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except Exception as e:
        log("stdin parse failed: %r" % e)
        data = {}
    if not isinstance(data, dict):
        data = {}
    try:
        cfg = load_config()
        title, tags, priority, body = classify(data)
        body = build_body(body, data)
        publish(cfg, title, tags, priority, body)
        log("posted | %s | prio=%s | %s" % (title, priority, body))
    except Exception as e:
        log("publish failed: %r" % e)


if __name__ == "__main__":
    main()
    sys.exit(0)
