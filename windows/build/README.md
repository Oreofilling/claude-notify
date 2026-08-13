# 打包说明

## 前置（开发机，Windows）
```bat
pip install -r requirements.txt pyinstaller
```

## 一键打包（onedir）
```bat
cd <项目根目录>
build\build.bat
```
产物：`dist\ClaudeNotify\ClaudeNotify.exe`（连同同目录 DLL/数据，整文件夹分发）。

## 手动打包
```bat
pyinstaller --noconfirm --windowed --name ClaudeNotify ^
  --hidden-import pystray._win32 ^
  --collect-all win11toast --collect-all winsdk main.py
```
（等价于 `build\ClaudeNotify.spec`）

## 注意
- 首次启动 exe 可能触发 SmartScreen（未签名）-> 点「更多信息」->「仍要运行」。
- 体积约 40-60MB（winsdk 较大）；onedir 比 onefile 启动快、误报少。
- 想做开始菜单图标避免 Toast 不弹：右键 exe -> 创建快捷方式 -> 放到「开始菜单\程序」。
