# -*- coding: utf-8 -*-
"""tkinter 设置 GUI。必须在独立线程运行（pystray 占主线程）。"""
import tkinter as tk
from tkinter import ttk, messagebox

from .constants import CATEGORIES

_CAT_LABEL = {"stop": "任务完成", "idle": "等待输入",
              "permission": "请求授权", "other": "其它通知"}


class SettingsDialog:
    def __init__(self, config, on_save):
        self._cfg = config
        self._on_save = on_save  # callable(new_cfg: Config)
        self._vars: dict = {}
        self._root = None

    def show(self) -> None:
        self._root = tk.Tk()
        self._root.title("Claude Notify 设置")
        self._root.geometry("480x460")
        self._root.resizable(False, False)
        self._build(self._root)
        self._root.mainloop()

    def _build(self, root: tk.Tk) -> None:
        c = self._cfg
        v = self._vars
        pad = {"padx": 10, "pady": 6}

        conn = ttk.LabelFrame(root, text="连接")
        conn.pack(fill="x", **pad)
        ttk.Label(conn, text="服务器地址").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        v["server_url"] = tk.StringVar(value=c.server_url)
        ttk.Entry(conn, textvariable=v["server_url"], width=34).grid(row=0, column=1, pady=6)
        ttk.Label(conn, text="Topic").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        v["topic"] = tk.StringVar(value=c.topic)
        ttk.Entry(conn, textvariable=v["topic"], width=34).grid(row=1, column=1, pady=6)
        ttk.Label(conn, text="Token（可选）").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        v["token"] = tk.StringVar(value=c.token)
        ttk.Entry(conn, textvariable=v["token"], width=34).grid(row=2, column=1, pady=6)

        cats = ttk.LabelFrame(root, text="启用哪些通知")
        cats.pack(fill="x", **pad)
        for i, key in enumerate(CATEGORIES):
            v["en_" + key] = tk.BooleanVar(value=bool(c.enabled.get(key, True)))
            ttk.Checkbutton(cats, text=_CAT_LABEL.get(key, key),
                            variable=v["en_" + key]).grid(row=0, column=i, padx=8, pady=6)

        snd = ttk.LabelFrame(root, text="声音与行为")
        snd.pack(fill="x", **pad)
        v["sound_default"] = tk.BooleanVar(value=c.sound_default)
        ttk.Checkbutton(snd, text="普通通知播放声音", variable=v["sound_default"]).pack(anchor="w", padx=8, pady=4)
        v["sound_urgent_loop"] = tk.BooleanVar(value=c.sound_urgent_loop)
        ttk.Checkbutton(snd, text="「请求授权」循环报警直到处理", variable=v["sound_urgent_loop"]).pack(anchor="w", padx=8, pady=4)
        v["autostart"] = tk.BooleanVar(value=c.autostart)
        ttk.Checkbutton(snd, text="开机自启", variable=v["autostart"]).pack(anchor="w", padx=8, pady=4)
        v["pause_all"] = tk.BooleanVar(value=c.pause_all)
        ttk.Checkbutton(snd, text="暂停全部通知", variable=v["pause_all"]).pack(anchor="w", padx=8, pady=4)
        ttk.Label(snd, text="历史记录条数").pack(side="left", padx=8, pady=6)
        v["history_size"] = tk.IntVar(value=c.history_size)
        ttk.Spinbox(snd, from_=50, to=2000, increment=50,
                    textvariable=v["history_size"], width=8).pack(side="left", pady=6)

        bar = ttk.Frame(root)
        bar.pack(fill="x", **pad)
        ttk.Button(bar, text="取消", command=self._cancel).pack(side="right", padx=6)
        ttk.Button(bar, text="保存", command=self._save).pack(side="right", padx=6)

    def _collect(self):
        from .config import Config
        v = self._vars
        c = Config()
        c.server_url = v["server_url"].get().strip()
        c.topic = v["topic"].get().strip()
        c.token = v["token"].get().strip()
        c.enabled = {k: v["en_" + k].get() for k in CATEGORIES}
        c.sound_default = v["sound_default"].get()
        c.sound_urgent_loop = v["sound_urgent_loop"].get()
        c.autostart = v["autostart"].get()
        c.pause_all = v["pause_all"].get()
        c.history_size = max(50, int(v["history_size"].get()))
        return c

    def _cancel(self) -> None:
        if self._root:
            self._root.destroy()

    def _save(self) -> None:
        if not self._vars["topic"].get().strip():
            messagebox.showwarning("缺少 Topic", "请填写 Topic（在服务器端 install.sh 打印的那串）。", parent=self._root)
            return
        cfg = self._collect()
        cfg.save()
        try:
            self._on_save(cfg)
        except Exception as e:
            messagebox.showerror("保存", "已保存，但应用时出错：%r" % e, parent=self._root)
        if self._root:
            self._root.destroy()
