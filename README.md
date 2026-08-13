# Claude Code → Windows 通知小程序

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue)](#)
[![Python](https://img.shields.io/badge/Python-3.8+-3776AB)](#)
[![Transport](https://img.shields.io/badge/transport-ntfy-3a9fff)](https://ntfy.sh)
[![Release](https://img.shields.io/github/v/release/Oreofilling/claude-notify)](https://github.com/Oreofilling/claude-notify/releases)
[![Stars](https://img.shields.io/github/stars/Oreofilling/claude-notify?style=social)](https://github.com/Oreofilling/claude-notify)

远程 Linux 服务器跑 Claude Code，**任务完成 / 等待输入 / 需要授权**时，自动在 Windows 弹原生 Toast。
Windows 无需公网 IP 或端口转发——通知经 **ntfy** 协议由 Windows 主动拉取，天然穿透 NAT。

```
远程 Linux 服务器                          Windows PC
┌──────────────────────┐                ┌──────────────────────────┐
│ Claude Code          │  POST 事件      │ ClaudeNotify.exe (托盘)  │
│  ├ Stop hook ──┐     │ ──(经 ntfy)──▶ │  ├ ntfy 订阅(后台线程)   │
│  └ Notification ┐    │                │  ├ 原生 Toast(分级声音)  │
│     hook 脚本   └────┤                │  ├ 设置 / 历史 GUI       │
│  (python3 零依赖)    │                │  └ 开机自启              │
└──────────────────────┘                └──────────────────────────┘
```

## 三类时机

| 时机 | 触发 | 通知 | 优先级 |
|------|------|------|--------|
| Claude 响应结束 | `Stop` 钩子 | 「Claude 任务完成」✅ | 普通 |
| Claude 等你输入 | `Notification(idle_prompt)` | 「Claude 等待输入」💬 | 高 |
| Claude 请求工具授权 | `Notification(permission_prompt)` | 「Claude 请求授权」🚨 | 紧急（常驻 + 循环报警，直到你处理）|

> 隐私：通知正文只含 **事件类型 + 项目名**（当前目录名），**绝不**包含代码 / 命令 / 文件路径 / 密钥。

---

## 一、服务器端安装（Linux）

### 默认：用公共 ntfy.sh（零部署）
```bash
# 1. 把 server/ 传到服务器
scp -r server/ user@your-server:~/claude-notify-hooks/

# 2. 登录服务器，安装
ssh user@your-server
cd ~/claude-notify-hooks
chmod +x install.sh
./install.sh
```
`install.sh` 会：
1. 用 `openssl rand -hex 12` 生成一个不可猜的 **topic**（公共 ntfy 下相当于密码）；
2. 写 `~/.config/claude-notify/config.json`（权限 600）；
3. 把 `Stop` / `Notification` 钩子**幂等合并**进 `~/.claude/settings.json`（保留你已有的钩子和配置，重装不重复）。

安装完会打印 topic，**记下它**，下一步填到 Windows App。

### 验证服务器端
```bash
# 手动触发一次 Stop 事件
echo '{"hook_event_name":"Stop","cwd":"/home/me/proj"}' \
  | python3 ~/claude-notify-hooks/claude_notify_hook.py

# 设了调试可看到分类日志
CLAUDE_NTFY_DEBUG=1 echo '{"hook_event_name":"Notification","notification_type":"permission_prompt","cwd":"/x"}' \
  | python3 ~/claude-notify-hooks/claude_notify_hook.py
# 预期 stderr: posted | Claude 请求授权 | prio=urgent | [x] ...
```
消息已发到 ntfy。若 Windows / 手机端正订阅该 topic，会秒级收到。

### 卸载
从 `~/.claude/settings.json` 的 `Stop` / `Notification` 数组里删掉指向 `claude_notify_hook.py` 的条目即可（重跑 `install.sh` 也会先移除旧的再加新的，可借它「重置」）。

---

## 二、Windows 端安装

### 方式 A：直接用打包好的 exe
拿到 `dist\ClaudeNotify\` 整个文件夹 → 双击 `ClaudeNotify.exe`：
- 首次启动自动弹**设置框**，填入服务器端打印的 topic（服务器地址默认 `https://ntfy.sh`，token 留空）→ 保存；
- 系统托盘出现蓝色「C」图标，开始订阅；
- 点托盘菜单「**发送测试通知**」可立即验证 Toast 是否正常（无需服务器参与）。

### 方式 B：自己打包
```bat
cd claude-notify-windows
pip install -r requirements.txt pyinstaller
build\build.bat
:: 产物：dist\ClaudeNotify\ClaudeNotify.exe
```
详见 `windows\build\README.md`。

### 托盘菜单
- 发送测试通知 / 历史记录 / 设置…
- 暂停全部通知（勾选）/ 开机自启（勾选，写注册表 `HKCU\…\Run`）
- 退出

### 图标状态
- 🔵 蓝「C」：已连接
- 🟠 橙「C」：有新通知未查看
- 🔴 红「!」：连接断开，指数退避重连中

---

## 三、后续拓展到 iPhone（一行配置）

ntfy 是标准协议，iPhone 装官方 **ntfy** App（App Store 免费）：
1. 打开 App → 添加订阅 → 输入**同一个 topic**；
2. （若服务器端设了 token）在 App 设置里填 token；
3. 完事。Claude 的事件会同时弹到 Windows 和 iPhone。

> iPhone 端无需任何代码改动——它就是 ntfy 的另一个订阅者。Windows 小程序和 iPhone 各自独立，互不影响。

---

## 四、想完全私有？自托管 ntfy（两端代码零改动）

公共 `ntfy.sh` 开箱即用，但消息过境第三方。要全程不出内网：

```bash
# 服务器上跑单文件 ntfy（Docker 示例）
docker run -d --name ntfy --restart=unless-stopped \
  -p 8090:80 -v /var/lib/ntfy:/var/lib/ntfy \
  binwiederhier/ntfy serve

# 加 HTTPS（nginx/caddy 反代 + 鉴权），略
```
然后：
1. 服务器端：编辑 `~/.config/claude-notify/config.json` 的 `url` 改成 `https://your-host:8090`（可加 access token）；
2. Windows 端：设置框里把「服务器地址」改成同一个自托管地址。

**钩子脚本和 Windows 代码都不用改**——端点 URL 全程可配置。

---

## 五、故障排查

| 现象 | 排查 |
|------|------|
| Windows 收不到通知 | 1) 托盘图标是否蓝色（连接）？红色则看服务器地址/topic 是否对；2) 设了 `CLAUDE_NTFY_DEBUG=1` 看服务器是否 `posted`；3) topic 必须两端完全一致 |
| 服务器报 `no topic configured` | `~/.config/claude-notify/config.json` 没生成或 topic 为空，重跑 `install.sh` |
| Toast 不弹（服务器确认已发） | Win11「专注助手/勿扰」是否开启？或 AppUserModelID 未注册→把 exe 快捷方式放进「开始菜单\程序」；或暂切 `Windows-Toasts` |
| exe 被 SmartScreen 拦 | 未签名所致，点「更多信息」→「仍要运行」；可自签名 |
| 通知把 JSON 当文本显示 | 已修复：服务器脚本 POST 到根路径 `/`（JSON 发布模式），请用仓库最新 `claude_notify_hook.py` |
| `permission_prompt` 没循环报警 | 设置里确认「请求授权循环报警」勾选；专注助手可能压制循环音 |
| 钩子拖慢 Claude | 已 `async:true` + 脚本 5s 超时 + 吞所有异常；最坏 5s 内返回，实测 <10ms |

### 手动核对 ntfy 消息（curl poll）
```bash
TOPIC=你生成的topic
curl -s "https://ntfy.sh/$TOPIC/json?poll=1" | python3 -c "
import sys,json
for l in sys.stdin:
    l=l.strip()
    if not l: continue
    m=json.loads(l)
    if m.get('event')=='message':
        print(m.get('priority'), m.get('title'), '|', m.get('message'))
"
# 期望看到独立的 title/priority/tags 字段（而非整段 JSON 被当文本）
```

---

## 六、项目结构
```
claude-notify/
├── README.md
├── server/                      # Linux 服务器端
│   ├── claude_notify_hook.py    # 零依赖钩子脚本（json + urllib）
│   └── install.sh               # 生成 topic、写 config、合并 settings.json
└── windows/                     # Windows 托盘小程序
    ├── main.py                  # 入口，装配 config+subscriber+tray
    ├── requirements.txt         # pystray / Pillow / win11toast / requests
    ├── app/
    │   ├── constants.py         # 优先级、类别、默认配置
    │   ├── config.py            # %APPDATA%\ClaudeNotify\config.json 读写
    │   ├── history.py           # 线程安全环形缓冲
    │   ├── subscriber.py        # ntfy 流式订阅 + 重连 + 心跳看门狗
    │   ├── notifier.py          # win11toast 分级 Toast
    │   ├── tray.py              # pystray 托盘/菜单/图标
    │   ├── settings_dialog.py   # tkinter 设置 GUI
    │   ├── history_dialog.py    # tkinter 历史查看
    │   └── autostart.py         # 注册表开机自启
    └── build/
        ├── ClaudeNotify.spec    # PyInstaller onedir
        ├── build.bat            # 一键打包
        └── README.md
```

## 安全要点
- Topic 用 `openssl rand` 生成（不可猜）；公共 ntfy 下相当于密码，**不要外泄**。
- `config.json` 权限 600；可选 access token 进一步鉴权（自托管时建议开启）。
- 通知不含任何代码/密钥/路径——即使 topic 泄露，泄露的也只是「Claude 在 X 项目完成了/等你输入」。
- `install.sh` 只**合并**你的 `settings.json`，解析失败先备份 `.bak`，绝不覆盖其它配置。
