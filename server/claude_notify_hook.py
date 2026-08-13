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
import time
import urllib.request

CONFIG_PATH = os.path.expanduser("~/.config/claude-notify/config.json")
DEFAULT_URL = "https://ntfy.sh"
TIMEOUT = 5  # 秒
EVENT_LOG = os.path.expanduser("~/.config/claude-notify/events.log")

# compact 抑制：PreCompact 钩子写一条「最近发生过 compact」的标记；
# 随后若 Stop 落在窗口内，即判定为 compact 摘要回合（无真实答案），跳过弹窗。
# 仅按会话 id 写标记文件，绝不读对话内容；标记一次性消费 + 过期自动清理。
COMPACT_DIR = os.path.expanduser("~/.config/claude-notify")
COMPACT_SUPPRESS_WINDOW = 180  # 秒


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


def resolve_label(cwd, cfg):
    """决定正文前缀里的项目名（只读目录/标记文件，绝不读对话内容）。

    优先级：
      1. 项目根 .claude-notify 标记文件（取首个非注释非空行，向上查找）
      2. config.project_labels: {绝对路径: 名字}
      3. 回退：cwd 末段目录名（与旧行为一致）
    """
    # 1. 向上查找 .claude-notify 标记文件
    if cwd:
        d = os.path.abspath(cwd)
        prev = None
        while d and d != prev:
            marker = os.path.join(d, ".claude-notify")
            try:
                if os.path.isfile(marker):
                    with open(marker, "r", encoding="utf-8") as f:
                        for line in f:
                            s = line.strip()
                            if s and not s.startswith("#"):
                                # 轻清洗：去方括号/截断，避免破坏 [..] 包裹
                                s = s.replace("[", "").replace("]", "")
                                return s[:40]
            except Exception:
                pass
            prev = d
            d = os.path.dirname(d)
    # 2. config 显式映射（绝对路径 -> 名字）
    labels = cfg.get("project_labels") if isinstance(cfg, dict) else None
    if cwd and isinstance(labels, dict):
        v = (labels.get(cwd) or "").strip()
        if v:
            return v[:40]
    # 3. 回退：目录名
    return (os.path.basename(cwd.rstrip("/")) if cwd else "")


def log_event(data, label, note=""):
    """只记元数据（不含消息正文/完整路径/字段值），用于定位 compact 等误触发。

    events.log 字段：时间 / hook_event_name / notification_type / stop_hook_active /
    label / last_assistant_message 长度与是否为空 / payload顶层键名 / 可选 note。
    """
    try:
        keys = ",".join(sorted(data.keys())) if isinstance(data, dict) else "-"
        lam = data.get("last_assistant_message")
        lam = lam if isinstance(lam, str) else ("" if lam is None else str(lam))
        line = "%s hook=%s ntype=%s stop_active=%s label=%s lam_len=%s lam_empty=%s keys=%s" % (
            time.strftime("%Y-%m-%d %H:%M:%S"),
            data.get("hook_event_name") or "-",
            data.get("notification_type") or "-",
            data.get("stop_hook_active"),
            label or "-",
            len(lam),
            str(not bool(lam.strip())),
            keys,
        )
        if note:
            line += " note=%s" % note
        line += "\n"
        with open(EVENT_LOG, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass


def _compact_marker_path(session_id):
    sid = (session_id or "").strip().replace("/", "_")
    if not sid:
        sid = "_global"
    return os.path.join(COMPACT_DIR, "compact-%s.marker" % sid)


def mark_compact(session_id):
    """PreCompact 触发：写一条时间戳标记，供随后的 Stop 判定是否为 compact 摘要回合。"""
    try:
        os.makedirs(COMPACT_DIR, exist_ok=True)
        with open(_compact_marker_path(session_id), "w", encoding="utf-8") as f:
            f.write("%.3f" % time.time())
    except Exception as e:
        log("mark_compact failed: %r" % e)


def consume_compact_stop(session_id):
    """Stop 触发：若本会话近期(<=COMPACT_SUPPRESS_WINDOW)有 PreCompact 标记，
    视为 compact 摘要回合 -> 返回 True（应跳过弹窗），并删除标记（一次性消费）。
    同时顺手清理 >1 小时的陈旧标记，避免堆积。

    判定只依赖标记文件的 mtime 与 session_id，绝不读 transcript / 消息正文。
    """
    now = time.time()
    # 顺手清理陈旧标记（>1h）
    try:
        for name in os.listdir(COMPACT_DIR):
            if not (name.startswith("compact-") and name.endswith(".marker")):
                continue
            p = os.path.join(COMPACT_DIR, name)
            try:
                if now - os.path.getmtime(p) > 3600:
                    os.remove(p)
            except Exception:
                pass
    except Exception:
        pass
    path = _compact_marker_path(session_id)
    try:
        if not os.path.isfile(path):
            return False
        fresh = (now - os.path.getmtime(path)) <= COMPACT_SUPPRESS_WINDOW
        os.remove(path)  # 一次性消费（命中或过期都删，避免重复抑制）
        return fresh
    except Exception as e:
        log("consume_compact_stop failed: %r" % e)
        return False


def build_body(base_body, label):
    """正文加项目名前缀（label 由 resolve_label 决定）。"""
    return ("[%s] %s" % (label, base_body)) if label else base_body


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
        label = resolve_label(data.get("cwd") or "", cfg)
        hook = (data.get("hook_event_name") or "").strip()

        # PreCompact：只写「最近 compact」标记 + 记日志，绝不发通知
        if hook == "PreCompact":
            mark_compact(data.get("session_id") or "")
            log_event(data, label, note="precompact_marker")
            log("precompact marker set | session=%s" % (data.get("session_id") or "-"))
            return

        # Stop：若是 compact 摘要回合（近期有 PreCompact 标记）-> 跳过弹窗
        if hook == "Stop" and consume_compact_stop(data.get("session_id") or ""):
            log_event(data, label, note="suppressed=compact")
            log("stop suppressed (compact summary) | session=%s" % (data.get("session_id") or "-"))
            return

        title, tags, priority, body = classify(data)
        body = build_body(body, label)
        log_event(data, label)
        publish(cfg, title, tags, priority, body)
        log("posted | %s | prio=%s | %s" % (title, priority, body))
    except Exception as e:
        log("publish failed: %r" % e)


if __name__ == "__main__":
    main()
    sys.exit(0)
