# Claude Code → Windows Notifier

> **Languages:** English | [简体中文](README.zh.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB)](#)
[![Transport](https://img.shields.io/badge/transport-ntfy-3a9fff)](https://ntfy.sh)
[![Release](https://img.shields.io/github/v/release/Oreofilling/claude-notify)](https://github.com/Oreofilling/claude-notify/releases)

Get native Windows toast notifications whenever Claude Code running on a **remote Linux server** finishes a task, waits for input, or requests a tool permission. Your Windows PC needs no public IP or port forwarding — notifications are pulled by Windows over the **ntfy** protocol, so they traverse NAT naturally.

```
Remote Linux server                         Windows PC
┌──────────────────────┐                ┌──────────────────────────┐
│ Claude Code          │  POST events    │ ClaudeNotify.exe (tray)  │
│  ├ Stop hook ──┐     │ ──(via ntfy)──▶ │  ├ ntfy subscriber (bg)  │
│  └ Notification ┐    │                 │  ├ native toast (leveled)│
│     hook script └────┤                 │  ├ settings / history UI │
│  (python3, zero-dep) │                 │  └ autostart             │
└──────────────────────┘                 └──────────────────────────┘
```

## Three trigger moments

| Moment | Trigger | Notification | Priority |
|--------|---------|--------------|----------|
| Claude finished responding | `Stop` hook | "Claude task complete" ✅ | Normal |
| Claude is waiting for input | `Notification(idle_prompt)` | "Claude awaits input" 💬 | High |
| Claude requests tool permission | `Notification(permission_prompt)` | "Claude requests permission" 🚨 | Urgent (persistent + looping alarm until you act) |

> **Privacy:** notification bodies contain **only the event type + project name** (the current directory name). They **never** include code, commands, file paths, or secrets.

---

## 1. Server-side install (Linux)

### Default: use public ntfy.sh (zero deployment)
```bash
# 1. Copy server/ to your server
scp -r server/ user@your-server:~/claude-notify-hooks/

# 2. SSH in and install
ssh user@your-server
cd ~/claude-notify-hooks
chmod +x install.sh
./install.sh
```
`install.sh` will:
1. Generate an unguessable **topic** with `openssl rand -hex 12` (acts as a password on public ntfy);
2. Write `~/.config/claude-notify/config.json` (chmod 600);
3. **Idempotently merge** the `Stop` / `Notification` hooks into `~/.claude/settings.json` (preserving your existing hooks and config; reinstalling won't duplicate).

It prints the topic at the end — **write it down**, you'll paste it into the Windows app next.

### Verify the server side
```bash
# Trigger a Stop event manually
echo '{"hook_event_name":"Stop","cwd":"/home/me/proj"}' \
  | python3 ~/claude-notify-hooks/claude_notify_hook.py

# With debug enabled you can see classification output
CLAUDE_NTFY_DEBUG=1 echo '{"hook_event_name":"Notification","notification_type":"permission_prompt","cwd":"/x"}' \
  | python3 ~/claude-notify-hooks/claude_notify_hook.py
# Expected stderr: posted | Claude requests permission | prio=urgent | [x] ...
```
The message is now published to ntfy. If a Windows / phone client is subscribed to that topic, it arrives within seconds.

### Uninstall
Remove the entries pointing to `claude_notify_hook.py` from the `Stop` / `Notification` arrays in `~/.claude/settings.json`. (Re-running `install.sh` also removes the old entries before re-adding, so you can use it to "reset".)

---

## 2. Windows-side install

### Option A: use the prebuilt exe
Grab the entire `dist\ClaudeNotify\` folder → double-click `ClaudeNotify.exe`:
- On first launch a **settings dialog** appears; paste the topic printed by the server (server URL defaults to `https://ntfy.sh`, token left empty) → save;
- A blue "C" icon appears in the system tray and starts subscribing;
- Tray menu **"Send test notification"** verifies the toast pipeline instantly (no server needed).

### Option B: build it yourself
```bat
cd claude-notify-windows
pip install -r requirements.txt pyinstaller
build\build.bat
:: Output: dist\ClaudeNotify\ClaudeNotify.exe
```
See `windows\build\README.md` for details.

### Tray menu
- Send test notification / History / Settings…
- Pause all notifications (checkbox) / Start with Windows (checkbox, writes registry `HKCU\…\Run`)
- Quit

### Icon states
- 🔵 blue "C": connected
- 🟠 orange "C": unread notifications
- 🔴 red "!": disconnected, reconnecting with exponential backoff

---

## 3. Extend to iPhone later (one config line)

ntfy is a standard protocol. Install the official **ntfy** app on iPhone (free on the App Store):
1. Open the app → add a subscription → enter the **same topic**;
2. (If the server uses a token) fill in the token in the app settings;
3. Done. Claude's events now pop on both Windows and iPhone.

> No code change is needed for iPhone — it is simply another ntfy subscriber. The Windows app and iPhone are independent and don't affect each other.

---

## 4. Want it fully private? Self-host ntfy (no code change on either side)

Public `ntfy.sh` works out of the box, but messages transit a third party. To keep everything inside your network:

```bash
# Run the single-binary ntfy on the server (Docker example)
docker run -d --name ntfy --restart=unless-stopped \
  -p 8090:80 -v /var/lib/ntfy:/var/lib/ntfy \
  binwiederhier/ntfy serve

# Add HTTPS (nginx/caddy reverse proxy + auth), omitted here
```
Then:
1. Server side: edit `url` in `~/.config/claude-notify/config.json` to `https://your-host:8090` (optionally add an access token);
2. Windows side: set "Server URL" in the settings dialog to the same self-hosted address.

**The hook script and Windows code don't change at all** — the endpoint URL is fully configurable.

---

## 5. Troubleshooting

| Symptom | Check |
|---------|-------|
| No notifications on Windows | 1) Is the tray icon blue (connected)? If red, verify server URL/topic; 2) Set `CLAUDE_NTFY_DEBUG=1` to confirm the server printed `posted`; 3) The topic must be identical on both ends |
| Server reports `no topic configured` | `~/.config/claude-notify/config.json` is missing or topic is empty — re-run `install.sh` |
| Toasts don't appear (server confirmed sent) | Is Windows 11 Focus Assist / Do Not Disturb on? Or AppUserModelID not registered → put a shortcut to the exe in Start Menu\Programs; or temporarily switch to `Windows-Toasts` |
| exe blocked by SmartScreen | It's unsigned — click "More info" → "Run anyway"; you can self-sign |
| Notification shows the JSON as text | Already fixed: the server script POSTs to the root `/` (JSON publish mode) — use the latest `claude_notify_hook.py` from this repo |
| `permission_prompt` has no looping alarm | Confirm "Permission request looping alarm" is checked in settings; Focus Assist may suppress the loop |
| Hook slows down Claude | It's `async:true` + a 5s script timeout + swallows all exceptions; returns within 5s worst case, measured <10ms |

### Manually inspect ntfy messages (curl poll)
```bash
TOPIC=your-generated-topic
curl -s "https://ntfy.sh/$TOPIC/json?poll=1" | python3 -c "
import sys,json
for l in sys.stdin:
    l=l.strip()
    if not l: continue
    m=json.loads(l)
    if m.get('event')=='message':
        print(m.get('priority'), m.get('title'), '|', m.get('message'))
"
# Expect separate title/priority/tags fields (not the whole JSON shown as text)
```

---

## 6. Project structure
```
claude-notify/
├── README.md
├── server/                      # Linux server side
│   ├── claude_notify_hook.py    # zero-dependency hook (json + urllib)
│   └── install.sh               # generate topic, write config, merge settings.json
└── windows/                     # Windows tray app
    ├── main.py                  # entry; wires config+subscriber+tray
    ├── requirements.txt         # pystray / Pillow / win11toast / requests
    ├── app/
    │   ├── constants.py         # priorities, categories, default config
    │   ├── config.py            # read/write %APPDATA%\ClaudeNotify\config.json
    │   ├── history.py           # thread-safe ring buffer
    │   ├── subscriber.py        # ntfy streaming subscribe + reconnect + heartbeat watchdog
    │   ├── notifier.py          # win11toast leveled toast
    │   ├── tray.py              # pystray tray / menu / icon states
    │   ├── settings_dialog.py   # tkinter settings GUI
    │   ├── history_dialog.py    # tkinter history view
    │   └── autostart.py         # registry autostart
    └── build/
        ├── ClaudeNotify.spec    # PyInstaller onedir
        ├── build.bat            # one-click build
        └── README.md
```

## Security notes
- The topic is generated with `openssl rand` (unguessable); on public ntfy it acts as a password — **don't leak it**.
- `config.json` is chmod 600; an optional access token adds authentication (recommended for self-hosting).
- Notifications contain no code/secrets/paths — even if the topic leaks, only "Claude finished / awaits input on project X" is exposed.
- `install.sh` only **merges** into your `settings.json`; on parse failure it backs up to `.bak` first and never overwrites other config.
