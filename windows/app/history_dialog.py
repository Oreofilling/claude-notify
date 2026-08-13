# -*- coding: utf-8 -*-
"""通知历史查看（tkinter Treeview）。"""
import time
import tkinter as tk
from tkinter import ttk

_PRIO_LABEL = {5: "‼ 紧急", 4: "! 高", 3: "· 普通"}
_CAT_LABEL = {"stop": "任务完成", "idle": "等待输入",
              "permission": "请求授权", "other": "其它"}


def show_history(history) -> None:
    root = tk.Tk()
    root.title("Claude Notify · 历史记录")
    root.geometry("620x420")
    cols = ("time", "category", "priority", "title", "body")
    tree = ttk.Treeview(root, columns=cols, show="headings")
    for c, w in zip(cols, (120, 90, 70, 160, 320)):
        tree.heading(c, text={"time": "时间", "category": "类别",
                              "priority": "优先级", "title": "标题", "body": "内容"}[c])
        tree.column(c, width=w, anchor="w")
    tree.pack(fill="both", expand=True, padx=8, pady=8)

    for it in history.latest(200):
        tree.insert("", "end", values=(
            time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(it.ts)),
            _CAT_LABEL.get(it.category, it.category),
            _PRIO_LABEL.get(it.priority, "· 普通"),
            it.title, it.body,
        ))

    ttk.Button(root, text="关闭", command=root.destroy).pack(pady=8)
    root.mainloop()
