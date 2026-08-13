#!/usr/bin/env bash
# Claude Code -> ntfy 通知桥：服务器端安装脚本
#
# 做三件事：
#   1. 生成不可猜的 ntfy topic（openssl rand，公共 ntfy.sh 下相当于密码），可复用已有
#   2. 写 ~/.config/claude-notify/config.json（chmod 600），含 url/topic/token
#   3. 把 Stop / Notification 钩子安全合并进 ~/.claude/settings.json（幂等，不破坏已有配置）
# 最后打印 topic 供 Windows App 粘贴。
#
# 安全：config.json 只含 topic（非密钥）；settings.json 合并用标准库 json 解析，
#       解析失败先备份 .bak 再继续；绝不删除用户其它配置。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK="$SCRIPT_DIR/claude_notify_hook.py"
CONFIG_DIR="$HOME/.config/claude-notify"
CONFIG="$CONFIG_DIR/config.json"
SETTINGS="$HOME/.claude/settings.json"

# ---------- 前置检查 ----------
need() { command -v "$1" >/dev/null 2>&1 || { echo "❌ 缺少依赖：$1" >&2; exit 1; }; }
need openssl
need python3
[[ -f "$HOOK" ]] || { echo "❌ 找不到钩子脚本：$HOOK（install.sh 须与 claude_notify_hook.py 同目录）" >&2; exit 1; }

# ---------- 1. topic（复用优先）----------
EXISTING_TOPIC=""
if [[ -f "$CONFIG" ]]; then
  EXISTING_TOPIC="$(python3 -c "import json,sys
try: print(json.load(open(sys.argv[1])).get('topic',''))
except Exception: print('')
" "$CONFIG" 2>/dev/null || true)"
fi
if [[ -n "$EXISTING_TOPIC" ]]; then
  TOPIC="$EXISTING_TOPIC"
  echo "♻️  复用已有 topic：$TOPIC"
else
  TOPIC="claude-$(openssl rand -hex 12)"
  echo "🔑 生成新 topic：$TOPIC"
fi

# ---------- 2. 写 config.json（600）----------
mkdir -p "$CONFIG_DIR"
python3 -c "
import json,sys,os
path,topic=sys.argv[1],sys.argv[2]
cfg={'url':'https://ntfy.sh','topic':topic,'token':''}
# 若已存在，保留用户填过的 token/url，只确保 topic 最新
if os.path.exists(path):
    try:
        old=json.load(open(path))
        if isinstance(old,dict):
            cfg['url']=old.get('url',cfg['url'])
            cfg['token']=old.get('token',cfg['token'])
    except Exception: pass
json.dump(cfg,open(path,'w'),indent=2,ensure_ascii=False)
" "$CONFIG" "$TOPIC"
chmod 600 "$CONFIG"
echo "📝 已写 $CONFIG（权限 600）"

# ---------- 3. 合并 hooks 到 settings.json（幂等）----------
PY="$(command -v python3)"
mkdir -p "$HOME/.claude"
python3 - "$SETTINGS" "$HOOK" "$PY" <<'PYEOF'
import json, sys, os
settings_path, hook_path, py_path = sys.argv[1], sys.argv[2], sys.argv[3]
cmd = "%s %s" % (py_path, hook_path)  # 绝对路径，Claude 任意工作目录都能找到

# 读取已有 settings.json；损坏则备份后从空开始
data = {}
if os.path.exists(settings_path):
    try:
        with open(settings_path, encoding="utf-8") as f:
            d = json.load(f)
        data = d if isinstance(d, dict) else {}
    except Exception:
        bak = settings_path + ".bak"
        try:
            os.replace(settings_path, bak)
            print("⚠️  settings.json 解析失败，已备份为 %s" % bak)
        except Exception:
            pass
        data = {}

hooks = data.setdefault("hooks", {})

def strip_ours(groups):
    """删除所有指向本钩子的 command，保留用户其它钩子；丢掉变空的 matcher 组。"""
    if not isinstance(groups, list):
        return []
    cleaned = []
    for g in groups:
        if not isinstance(g, dict):
            cleaned.append(g); continue
        inner = g.get("hooks")
        if not isinstance(inner, list):
            cleaned.append(g); continue
        keep = [h for h in inner
                if not (isinstance(h, dict) and hook_path in str(h.get("command", "")))]
        if keep:
            g2 = dict(g); g2["hooks"] = keep
            cleaned.append(g2)
    return cleaned

# Stop：无 matcher（每次响应结束都触发）
# Notification：省略 matcher -> 捕获全部 notification_type
new_group = {"hooks": [{"type": "command", "command": cmd, "timeout": 10, "async": True}]}
for event in ("Stop", "Notification"):
    hooks[event] = strip_ours(hooks.get(event)) + [new_group]

with open(settings_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
print("🔧 已合并 Stop/Notification 钩子到 %s" % settings_path)
PYEOF

echo
echo "═════════════════════════════════════════════════════"
echo "  ✅ 安装完成"
echo
echo "  在 Windows App 的设置里填："
echo "    服务器地址 : https://ntfy.sh"
echo "    Topic      : $TOPIC"
echo "    Token      : （公共 ntfy.sh 留空即可）"
echo
echo "  测试服务器端是否打通："
echo "    echo '{\"hook_event_name\":\"Stop\",\"cwd\":\"/tmp\"}' | python3 $HOOK"
echo "  （随后 Windows / 手机应收到「Claude 任务完成」通知）"
echo "═════════════════════════════════════════════════════"
