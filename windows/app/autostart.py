# -*- coding: utf-8 -*-
"""开机自启：注册表 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。

冻结(PyInstaller)后 sys.executable 即 exe 路径。
"""
import sys

_NAME = "ClaudeNotify"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, _NAME)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_enabled(enabled: bool, exe_path: str = None) -> bool:
    try:
        import winreg
        path = exe_path or sys.executable
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if enabled:
                winreg.SetValueEx(k, _NAME, 0, winreg.REG_SZ, '"%s"' % path)
            else:
                try:
                    winreg.DeleteValue(k, _NAME)
                except FileNotFoundError:
                    pass
        return True
    except Exception:
        return False
