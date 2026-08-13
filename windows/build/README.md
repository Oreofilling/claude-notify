# Packaging Guide

## Prerequisites (dev machine, Windows)
```bat
pip install -r requirements.txt pyinstaller
```

## One-click build (onedir)
```bat
cd <project-root>
build\build.bat
```
Output: `dist\ClaudeNotify\ClaudeNotify.exe` (along with sibling DLLs/data in the same folder — distribute the whole folder).

## Manual build
```bat
pyinstaller --noconfirm --windowed --name ClaudeNotify ^
  --hidden-import pystray._win32 ^
  --collect-all win11toast --collect-all winsdk main.py
```
(Equivalent to `build\ClaudeNotify.spec`)

## Notes
- First launch of the exe may trigger SmartScreen (unsigned) → "More info" → "Run anyway".
- Size is about 40–60MB (winsdk is large); onedir starts faster than onefile and triggers fewer false positives.
- To add a Start Menu icon and avoid toasts not appearing: right-click the exe → Create shortcut → place it under "Start Menu\Programs".
