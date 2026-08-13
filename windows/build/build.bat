@echo off
REM ClaudeNotify Windows 打包脚本（onedir）
REM 用法：在项目根目录(claude-notify-windows\)执行 build\build.bat
REM 前置：pip install -r requirements.txt pyinstaller
setlocal
cd /d "%~dp0\.."
echo === 安装依赖 ===
python -m pip install -r requirements.txt pyinstaller || goto :err
echo === 打包（onedir） ===
python -m PyInstaller --noconfirm build\ClaudeNotify.spec || goto :err
echo.
echo === 完成 ===
echo 产物：dist\ClaudeNotify\ClaudeNotify.exe
echo 把整个 dist\ClaudeNotify\ 文件夹拷给用户，双击 exe 即可。
goto :eof
:err
echo 打包失败。exit /b 1
