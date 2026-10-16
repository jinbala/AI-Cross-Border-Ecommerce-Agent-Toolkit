"""Native Windows desktop UI. Run with python -m desktop_app.app."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import os
from pathlib import Path
import queue
import re
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import traceback

if __package__:
    from . import core, selection
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from desktop_app import core, selection

BG = "#F4F6F9"
WHITE = "#FFFFFF"
INK = "#182230"
MUTED = "#667085"
ACCENT = "#2563EB"
PALE = "#EFF4FF"
LINE = "#E4E7EC"
DARK = "#FFFFFF"
ORANGE = "#B65B16"
FONT = "Microsoft YaHei UI"


def label(parent, text, size=10, color=INK, bold=False, bg=None, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, "bold" if bold else "normal"),
                    fg=color, bg=bg or parent.cget("bg"), **kwargs)


def button(parent, text, command, primary=False, **kwargs):
    normal, hover = (ACCENT, "#1D4ED8") if primary else (WHITE, "#F2F4F7")
    widget = tk.Button(parent, text=text, command=command, font=(FONT, 10),
                       bg=normal, fg=WHITE if primary else INK,
                       activebackground=hover, activeforeground=WHITE if primary else INK,
                       relief="flat", borderwidth=0, highlightthickness=1,
                       highlightbackground=ACCENT if primary else LINE, highlightcolor=ACCENT,
                       padx=14, pady=8, cursor="hand2", disabledforeground="#98A2B3", **kwargs)
    widget.bind("<Enter>", lambda e: widget.configure(bg=hover) if str(widget.cget("state")) != "disabled" else None)
    widget.bind("<Leave>", lambda e: widget.configure(bg=normal))
    return widget


def frame(parent, bg=WHITE, **kwargs):
    return tk.Frame(parent, bg=bg, **kwargs)


def text_area(parent, height=8, readonly=False):
    wrap = frame(parent)
    text = tk.Text(wrap, height=height, wrap="word", font=(FONT, 10), bg=WHITE, fg=INK,
                   relief="flat", borderwidth=0, padx=12, pady=10, undo=True,
                   insertbackground=ACCENT, selectbackground="#DBEAFE", spacing1=3, spacing3=3)
    bar = ttk.Scrollbar(wrap, command=text.yview)
    text.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    text.pack(side="left", fill="both", expand=True)
    if readonly:
        text.configure(state="disabled")
    return wrap, text


def put(text, value):
    state = str(text.cget("state"))
    text.configure(state="normal")
    text.delete("1.0", "end")
    text.insert("1.0", value)
    text.configure(state=state)


def content(text):
    return text.get("1.0", "end-1c").strip()


def scroller(parent, bg=BG):
    outer = frame(parent, bg)
    canvas = tk.Canvas(outer, bg=bg, highlightthickness=0)
    bar = ttk.Scrollbar(outer, command=canvas.yview)
    inner = frame(canvas, bg)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    bar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    outer.pack(fill="both", expand=True)
    return inner, canvas


def entry_field(parent, title, variable=None, values=None, row=None, column=0):
    box = frame(parent, parent.cget("bg"))
    label(box, title, 9, MUTED).pack(anchor="w", pady=(0, 6))
    variable = variable or tk.StringVar()
    if values:
        widget = ttk.Combobox(box, textvariable=variable, values=values, state="readonly", font=(FONT, 10))
    else:
        widget = ttk.Entry(box, textvariable=variable, font=(FONT, 10))
    widget.pack(fill="x", ipady=5)
    if row is not None:
        box.grid(row=row, column=column, sticky="ew", padx=(0, 16), pady=(0, 15))
    return box, variable, widget


def safe_name(value):
    result = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(". ")[:80]
    return result or "未命名资料"


class Workbench(tk.Tk):
    def __init__(self, data_dir=None):
        super().__init__()
        self.title(f"{core.APP_NAME}  {core.VERSION}")
        width = min(1380, max(1040, self.winfo_screenwidth() - 80))
        height = min(880, max(640, self.winfo_screenheight() - 100))
        self.geometry(f"{width}x{height}")
        self.minsize(1040, 640)
        self.configure(bg=BG)
        try:
            self.iconbitmap(str(core.ROOT / "desktop_app" / "assets" / "app.ico"))
        except tk.TclError:
            pass
        self.option_add("*Font", (FONT, 10))
        self.option_add("*TCombobox*Listbox.font", (FONT, 10))
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure("TEntry", fieldbackground=WHITE, foreground=INK, padding=6, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE)
        self.style.configure("TCombobox", fieldbackground=WHITE, background=WHITE, foreground=INK, padding=6, arrowcolor=ACCENT, bordercolor=LINE)
        self.style.map("TCombobox", fieldbackground=[("readonly", WHITE)], selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", INK)])
        self.style.configure("Treeview", font=(FONT, 10), rowheight=42, background=WHITE, fieldbackground=WHITE, foreground=INK, borderwidth=0)
        self.style.configure("Treeview.Heading", font=(FONT, 9), background="#F8FAFC", foreground=MUTED, relief="flat", padding=(12, 10))
        self.style.map("Treeview.Heading", background=[("active", "#EFF2F6")])
        self.style.map("Treeview", background=[("selected", "#E8F0FE")], foreground=[("selected", "#174EA6")])
        self.style.configure("TNotebook", background=BG, borderwidth=0)
        self.style.configure("TNotebook.Tab", font=(FONT, 10), padding=(18, 9), background=BG, foreground=MUTED)
        self.style.map("TNotebook.Tab", background=[("selected", WHITE)], foreground=[("selected", ACCENT)])
        self.style.configure("Vertical.TScrollbar", background=LINE, troughcolor=BG, borderwidth=0, arrowsize=12)
        self.store = core.Store(data_dir or core.default_data_dir())
        self.api_key = core.unprotect_key(self.store.setting("api_key", ""))
        self.events = queue.Queue()
        self.ai_running = False
        self.close_guard = None
        self.screen = None
        self.nav_buttons = {}
        self.nav_rows = {}
        self.status = tk.StringVar(value="本地工作台已就绪")
        self.sidebar()
        self.main = frame(self, BG)
        self.main.pack(side="left", fill="both", expand=True)
        footer = frame(self.main, BG)
        footer.pack(side="bottom", fill="x", padx=24, pady=(8, 10))
        label(footer, "●  数据保存在本机", 8, MUTED).pack(side="left")
        label(footer, "", 9, MUTED, textvariable=self.status).pack(side="right")
        self.page = frame(self.main, BG)
        self.page.pack(fill="both", expand=True)
        self.bind_all("<MouseWheel>", self.wheel, add=True)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(150, self.drain)
        self.show("dashboard")

    def sidebar(self):
        side = frame(self, WHITE, width=184, highlightbackground=LINE, highlightthickness=1)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = frame(side)
        logo.pack(fill="x", padx=18, pady=(26, 26))
        label(logo, "衣", 16, WHITE, True, ACCENT, padx=8, pady=3).pack(side="left", padx=(0, 9))
        brand = frame(logo)
        brand.pack(side="left")
        label(brand, "服装生意", 12, INK, True).pack(anchor="w")
        label(brand, "工厂经营工作台", 8, MUTED).pack(anchor="w", pady=(3, 0))
        menus = [("dashboard", "工作概览"), ("selection", "选品清单"), ("products", "产品档案"), ("pricing", "报价与利润"),
                 ("workflows", "AI 工作流"), ("analytics", "数据分析"),
                 ("experiments", "业务试验"), ("artifacts", "成果资料库")]
        for index, (key, title) in enumerate(menus):
            if index in (0, 4):
                label(side, "日常工作" if index == 0 else "分析与资料", 8, MUTED).pack(anchor="w", padx=22, pady=(14 if index else 0, 10))
            row = frame(side)
            row.pack(fill="x", padx=10, pady=3)
            icon = self.nav_icon(row, key)
            icon.pack(side="left", padx=(12, 4))
            b = tk.Button(row, text=title, anchor="w", command=lambda k=key: self.show(k),
                          bg=WHITE, fg=MUTED, activebackground=PALE, activeforeground=ACCENT,
                          font=(FONT, 10), relief="flat", borderwidth=0, padx=7, pady=11, cursor="hand2")
            b.pack(side="left", fill="x", expand=True)
            icon.bind("<Button-1>", lambda e, k=key: self.show(k))
            self.nav_buttons[key] = b
            self.nav_rows[key] = (row, icon)
        bottom = frame(side)
        bottom.pack(side="bottom", fill="x", padx=18, pady=20)
        button(bottom, "设置与备份", lambda: self.show("settings")).pack(fill="x")
        label(bottom, f"桌面版 {core.VERSION}", 8, MUTED).pack(anchor="w", pady=(14, 0))

    def nav_icon(self, parent, kind):
        """Small vector icons keep the packaged application crisp without image assets."""
        c = tk.Canvas(parent, width=20, height=20, bg=WHITE, highlightthickness=0, cursor="hand2")
        opts = dict(fill=MUTED, width=1.5)
        if kind == "dashboard":
            for x, y in ((3, 3), (12, 3), (3, 12), (12, 12)):
                c.create_rectangle(x, y, x + 5, y + 5, outline=MUTED, tags="outline")
        elif kind in ("selection", "products"):
            c.create_rectangle(4, 4, 16, 17, outline=MUTED, tags="outline")
            c.create_line(7, 2, 13, 2, 13, 6, 7, 6, 7, 2, **opts, tags="stroke")
            c.create_line(7, 10, 13, 10, **opts, tags="stroke")
            c.create_line(7, 13, 11, 13, **opts, tags="stroke")
        elif kind == "pricing":
            c.create_oval(2, 2, 18, 18, outline=MUTED, tags="outline")
            c.create_text(10, 10, text="¥", font=(FONT, 10), fill=MUTED, tags="stroke")
        elif kind == "workflows":
            c.create_line(11, 2, 4, 11, 10, 11, 9, 18, 17, 8, 11, 8, 11, 2, **opts, tags="stroke")
        elif kind == "analytics":
            for x, y in ((4, 12), (10, 7), (16, 3)):
                c.create_line(x, y, x, 17, **opts, tags="stroke")
        elif kind == "experiments":
            c.create_line(7, 2, 13, 2, 12, 2, 12, 8, 17, 17, 3, 17, 8, 8, 8, 2, **opts, tags="stroke")
            c.create_line(6, 12, 14, 12, **opts, tags="stroke")
        else:
            c.create_line(2, 5, 8, 5, 10, 7, 18, 7, 18, 17, 2, 17, 2, 5, **opts, tags="stroke")
        return c

    def wheel(self, event):
        widget = self.winfo_containing(event.x_root, event.y_root)
        if not widget:
            return
        if isinstance(widget, (tk.Text, ttk.Treeview, tk.Listbox, ttk.Combobox)):
            return
        while widget:
            if isinstance(widget, tk.Canvas):
                widget.yview_scroll(int(-event.delta / 120), "units")
                break
            widget = widget.master

    def tell(self, text):
        self.status.set(text)

    def fail(self, error):
        messagebox.showerror("请检查", str(error), parent=self)

    def guarded(self):
        return self.close_guard is None or self.close_guard()

    def show(self, name):
        if not self.guarded():
            return False
        self.close_guard = None
        self.screen = name
        for child in self.page.winfo_children():
            child.destroy()
        for key, b in self.nav_buttons.items():
            active = key == name or (key == "selection" and name == "selection_advanced")
            b.configure(bg=PALE if active else WHITE, fg=ACCENT if active else MUTED,
                        font=(FONT, 10, "bold" if active else "normal"))
            row, icon = self.nav_rows[key]
            row.configure(bg=PALE if active else WHITE)
            icon.configure(bg=PALE if active else WHITE)
            icon.itemconfigure("stroke", fill=ACCENT if active else MUTED)
            icon.itemconfigure("outline", outline=ACCENT if active else MUTED)
        getattr(self, f"view_{name}")()
        return True

    def heading(self, eyebrow, title, subtitle, action=None):
        head = frame(self.page, BG)
        head.pack(fill="x", padx=24, pady=(24, 20))
        if action:
            button(head, action[0], action[1], True).pack(side="right", padx=(15, 0), pady=3)
        label(head, title, 20, INK, True).pack(anchor="w", pady=(0, 6))
        sub = label(head, subtitle, 9, MUTED, justify="left", wraplength=700)
        sub.pack(anchor="w", fill="x")
        sub.bind("<Configure>", lambda e: sub.configure(wraplength=max(250, e.width)))
        body = frame(self.page, BG)
        body.pack(fill="both", expand=True, padx=24)
        return body

    def card(self, parent, title, amount, foot, column, color=INK):
        parent.grid_columnconfigure(column, weight=1, uniform="cards")
        c = frame(parent, WHITE, highlightbackground=LINE, highlightthickness=1)
        c.grid(row=0, column=column, sticky="nsew", padx=(0, 12 if column < 2 else 0))
        label(c, title, 10, MUTED).pack(anchor="w", padx=20, pady=(18, 8))
        label(c, amount, 27, color, True).pack(anchor="w", padx=20)
        label(c, foot, 9, MUTED).pack(anchor="w", padx=20, pady=(8, 18))

    def view_dashboard(self):
        body = self.heading("", "工作概览", "收集款式、算清利润，记录每一次新业务尝试。")
        wrap, _ = scroller(body)
        hero = frame(wrap, WHITE, highlightbackground=LINE, highlightthickness=1)
        hero.pack(fill="x", pady=(0, 20))
        left = frame(hero, WHITE)
        left.pack(side="left", padx=24, pady=22)
        label(left, "今天，先看一个新款", 16, INK, True).pack(anchor="w")
        label(left, "款名或链接就能开始，资料可以逐步补齐。", 10, MUTED).pack(anchor="w", pady=(9, 0))
        button(hero, "打开选品清单", lambda: self.show("selection"), True).pack(side="right", padx=24)
        products, artifacts, experiments = (self.store.list(k) for k in ("product", "artifact", "experiment"))
        month = core.now()[:7]
        spent = sum(float(x.get("spent", 0)) for x in experiments if str(x.get("date", x["created"]))[:7] == month)
        budget = float(self.store.setting("monthly_budget", 3000))
        stats = frame(wrap, BG)
        stats.pack(fill="x", pady=(0, 23))
        self.card(stats, "已收集选品", str(len(self.store.list("candidate"))), f"另有 {len(products)} 款产品档案", 0)
        self.card(stats, "本月试验支出", f"¥ {spent:,.0f}", f"月度预算 ¥ {budget:,.0f} · 按实际支出记录", 1, ORANGE if spent > budget else ACCENT)
        self.card(stats, "已保存成果", str(len(artifacts)), "任务包、文案与分析报告", 2)
        label(wrap, "常用工具", 12, INK, True).pack(anchor="w", pady=(0, 13))
        tasks = frame(wrap, BG)
        tasks.pack(fill="x", pady=(0, 22))
        for i, (title, desc, route) in enumerate([
            ("产品档案", "管理面料、尺码、交期与成本。", "products"),
            ("报价与利润", "测算供货报价和自营销售利润。", "pricing"),
            ("AI 工作流", "准备市场调研与商品文案。", "workflows"),
        ]):
            tasks.grid_columnconfigure(i, weight=1, uniform="tasks")
            c = frame(tasks, WHITE, highlightbackground=LINE, highlightthickness=1)
            c.grid(row=0, column=i, sticky="nsew", padx=(0, 12 if i < 2 else 0))
            label(c, title, 11, INK, True).pack(anchor="w", padx=18, pady=(18, 10))
            label(c, desc, 9, MUTED, wraplength=240, justify="left").pack(anchor="w", padx=18)
            button(c, "开始  →", lambda r=route: self.show(r)).pack(anchor="w", padx=18, pady=16)
        label(wrap, "最近的业务试验", 12, INK, True).pack(anchor="w", pady=(0, 12))
        if not experiments:
            empty = frame(wrap, WHITE)
            empty.pack(fill="x")
            label(empty, "还没有试验记录", 11, INK, True).pack(anchor="w", padx=20, pady=(18, 7))
            label(empty, "给新渠道设一个小目标，记录实际支出、收入和下一步动作。", 10, MUTED).pack(anchor="w", padx=20)
            button(empty, "记录第一个试验", lambda: self.show("experiments")).pack(anchor="w", padx=20, pady=16)
        else:
            for x in experiments[:3]:
                r = frame(wrap, WHITE)
                r.pack(fill="x", pady=(0, 5))
                label(r, x.get("name", "未命名"), 10, INK, True).pack(side="left", padx=18, pady=13)
                label(r, f"{x.get('channel', '')}  ·  {x.get('status', '计划中')}", 9, MUTED).pack(side="right", padx=18)
        label(wrap, "基础功能离线可用。AI 接口按需配置，商品资料只在你主动点击生成时发送。", 9, MUTED).pack(anchor="w", pady=(18, 12))

    def view_products(self):
        body = self.heading("Product library", "产品档案", "让面料、尺码、报价与交付信息都有一份可靠底稿。")
        left = frame(body, WHITE, width=245)
        left.pack(side="left", fill="y", padx=(0, 18))
        left.pack_propagate(False)
        label(left, "我的款式", 11, INK, True).pack(anchor="w", padx=16, pady=15)
        search = tk.StringVar()
        ttk.Entry(left, textvariable=search, font=(FONT, 10)).pack(fill="x", padx=14, ipady=5)
        self.product_list = tk.Listbox(left, font=(FONT, 10), bg=WHITE, fg=INK, selectbackground=PALE,
                                      selectforeground=ACCENT, relief="flat", borderwidth=0, highlightthickness=0,
                                      activestyle="none", exportselection=False)
        self.product_list.pack(fill="both", expand=True, padx=8, pady=12)
        button(left, "+  新建产品", lambda: select_product(None), True).pack(fill="x", padx=14, pady=(0, 14))
        right = frame(body, BG)
        right.pack(side="left", fill="both", expand=True)
        bottom = frame(right, BG)
        bottom.pack(side="bottom", fill="x", pady=(12, 4))
        inner, canvas = scroller(right)
        form = frame(inner, WHITE)
        form.pack(fill="x")
        label(form, "基本资料", 13, INK, True).pack(anchor="w", padx=20, pady=(18, 16))
        grid = frame(form)
        grid.pack(fill="x", padx=(20, 4))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        self.product_vars = {}
        self.product_texts = {}
        for i, (key, title) in enumerate(core.PRODUCT_FIELDS):
            _, var, _ = entry_field(grid, title + (" *" if key == "name" else ""), row=i // 2, column=i % 2)
            self.product_vars[key] = var
        for key, title in core.LONG_FIELDS:
            label(form, title, 9, MUTED).pack(anchor="w", padx=20, pady=(5, 6))
            w, text = text_area(form, 3)
            w.configure(highlightthickness=1, highlightbackground=LINE)
            w.pack(fill="x", padx=20, pady=(0, 14))
            self.product_texts[key] = text
        label(form, "不确定的信息可以留空。资料只能校验一致性，真实性需要实物或供应记录支持。", 9, MUTED, wraplength=620, justify="left").pack(anchor="w", padx=20, pady=(0, 20))
        self.edit_product_id = None
        self.product_original = {}

        def values():
            return {**{k: v.get().strip() for k, v in self.product_vars.items()}, **{k: content(t) for k, t in self.product_texts.items()}}

        def refresh_list():
            self.visible_products = [p for p in self.store.list("product") if search.get().lower() in (p.get("name", "") + p.get("sku", "")).lower()]
            self.product_list.delete(0, "end")
            for p in self.visible_products:
                self.product_list.insert("end", f"  {p.get('name', '未命名')}  {p.get('sku', '')}")

        def save():
            data = values()
            if not data["name"]:
                self.fail("请先填写款式名称。")
                return False
            try:
                for key in ("cost", "supply_price", "retail_price"):
                    if data[key]:
                        core.number(data[key], dict(core.PRODUCT_FIELDS)[key])
                self.edit_product_id = self.store.save("product", data, self.edit_product_id)
                self.product_original = data
                refresh_list()
                self.tell("产品档案已保存")
                return True
            except (ValueError, OSError) as e:
                self.fail(e)
                return False

        def guard():
            if values() == self.product_original:
                return True
            choice = messagebox.askyesnocancel("保存资料", "当前产品有未保存的修改。是否保存后继续？", parent=self)
            if choice is None:
                return False
            return save() if choice else True

        def select_product(product):
            if not guard():
                return
            self.edit_product_id = product.get("id") if product else None
            for key, var in self.product_vars.items():
                var.set((product or {}).get(key, ""))
            for key, text in self.product_texts.items():
                put(text, (product or {}).get(key, ""))
            self.product_original = values()
            canvas.yview_moveto(0)

        def selected(event):
            index = self.product_list.curselection()
            if index:
                select_product(self.visible_products[index[0]])

        def remove():
            if self.edit_product_id and messagebox.askyesno("删除产品", "删除当前产品档案？已保存成果和试验记录会保留。", parent=self):
                self.store.delete(self.edit_product_id)
                self.product_original = values()
                select_product(None)
                refresh_list()

        def export():
            if not values()["name"]:
                self.fail("请先填写产品资料。")
                return
            self.export_text(f"# 产品资料卡\n\n{core.product_text(values())}", values()["name"] + "_资料卡")

        self.product_original = values()
        self.close_guard = guard
        button(bottom, "保存档案", save, True).pack(side="right")
        button(bottom, "导出资料卡", export).pack(side="right", padx=10)
        button(bottom, "删除", remove).pack(side="left")
        self.product_list.bind("<<ListboxSelect>>", selected)
        search.trace_add("write", lambda *_: refresh_list())
        refresh_list()
        if self.visible_products:
            select_product(self.visible_products[0])

    def product_selector(self, parent, title="关联产品（可选）"):
        products = self.store.list("product")
        names = ["不关联产品"] + [f"{p.get('name', '未命名')}  ·  {p.get('sku') or p['id'][:6]}" for p in products]
        var = tk.StringVar(value=names[0])
        box, _, widget = entry_field(parent, title, var, names)
        box.pack(fill="x", pady=(0, 14))

        def selected():
            index = names.index(var.get()) if var.get() in names else 0
            return products[index - 1] if index else None
        return selected, widget

    def view_selection(self):
        body = self.heading("", "选品清单", "先收集想做的款，再逐步验证市场和利润。")
        scope = {}
        for key in ("platform", "market", "currency", "date"):
            scope[key] = tk.StringVar(value=self.store.setting("selection_" + key, ""))
        draft = self.store.setting("quick_selection_draft", "")
        dialog = None
        paste = None
        summary = tk.StringVar()
        filter_value = tk.StringVar(value="全部")
        search = tk.StringVar()
        toolbar = frame(body, BG)
        toolbar.pack(fill="x", pady=(0, 16))
        button(toolbar, "+  添加选品", lambda: open_intake(), True).pack(side="left", padx=(0, 8))
        button(toolbar, "粘贴并整理", lambda: clipboard()).pack(side="left", padx=(0, 8))
        button(toolbar, "导入 Excel", lambda: choose_file()).pack(side="left")
        button(toolbar, "条件筛选", lambda: self.show("selection_advanced")).pack(side="right")
        panel = frame(body, WHITE, highlightbackground=LINE, highlightthickness=1)
        panel.pack(fill="both", expand=True)
        list_head = frame(panel)
        list_head.pack(fill="x", padx=18, pady=(16, 12))
        filter_buttons = {}
        for title in ("全部", "待调研", "初筛匹配"):
            b = tk.Button(list_head, text=title, font=(FONT, 10), relief="flat", borderwidth=0,
                          padx=12, pady=7, cursor="hand2", command=lambda t=title: change_filter(t))
            b.pack(side="left", padx=(0, 4))
            filter_buttons[title] = b
        search_box = frame(list_head)
        search_box.pack(side="right")
        label(search_box, "搜索", 9, MUTED).pack(side="left", padx=(0, 8))
        search_entry = ttk.Entry(search_box, textvariable=search, width=23)
        search_entry.pack(side="left")
        label(panel, "", 9, MUTED, textvariable=summary).pack(anchor="w", padx=20, pady=(0, 12))
        table_host = frame(panel)
        table_host.pack(fill="both", expand=True, padx=6)
        tree = self.tree(table_host, [("name", "款式 / 商品线索", 350), ("source", "平台 / 站点", 160), ("status", "进度", 120)])
        tree.tag_configure("pending", foreground=MUTED)
        tree.tag_configure("matched", foreground="#18794E")
        empty = frame(table_host)
        empty_inner = frame(empty)
        empty_inner.pack(expand=True)
        label(empty_inner, "从一个想做的款开始", 15, INK, True).pack(pady=(0, 10))
        empty_message = tk.StringVar(value="写个款名、粘贴链接，或者直接导入表格。")
        label(empty_inner, "", 10, MUTED, textvariable=empty_message).pack()
        detail_panel = frame(panel)
        detail_panel.pack(side="bottom", before=table_host, fill="x", padx=18, pady=(12, 14))
        divider = frame(detail_panel, LINE, height=1)
        divider.pack(fill="x", pady=(0, 12))
        detail_title = tk.StringVar(value="选中一款，查看资料与下一步")
        detail_head = frame(detail_panel)
        detail_head.pack(fill="x")
        label(detail_head, "", 11, INK, True, textvariable=detail_title).pack(side="left")
        review_button = button(detail_head, "继续 AI 调研", lambda: review(), True)
        review_button.pack(side="right")
        review_button.configure(state="disabled")
        detail_wrap, detail = text_area(detail_panel, 3, True)
        detail_wrap.pack(fill="x", pady=(6, 0))
        put(detail, "清单自动保存在本机。选中商品后，可以查看来源、筛选依据并继续调研。")
        scope_line = frame(body, BG)
        scope_line.pack(side="bottom", before=panel, fill="x", pady=(10, 2))
        scope_summary = tk.StringVar()
        source_note = label(scope_line, "", 8, MUTED, textvariable=scope_summary, wraplength=700, justify="left")
        source_note.pack(anchor="w", fill="x")
        source_note.bind("<Configure>", lambda e: source_note.configure(wraplength=max(250, e.width)))

        def summary_scope(*args):
            values = [v.get().strip() for v in scope.values() if v.get().strip()]
            scope_summary.set("当前来源：" + " / ".join(values) if values else "可先收集款名和链接，来源信息后续补充。")
        for value in scope.values():
            value.trace_add("write", summary_scope)
        summary_scope()

        def metadata():
            result = {k: v.get().strip() for k, v in scope.items()}
            for key, value in result.items():
                self.store.set_setting("selection_" + key, value)
            return dict(as_of=result["date"], platform=result["platform"], market=result["market"], currency=result["currency"])

        def refresh(*args):
            needle = search.get().casefold()
            chosen = tree.selection()
            for row in tree.get_children():
                tree.delete(row)
            rows = self.store.list("candidate")
            visible = [item for item in rows if needle in (item["name"] + " " + item["source_id"]).casefold()]
            if filter_value.get() == "待调研":
                visible = [item for item in visible if item["strategy"] == "manual_lead" or item["status"] == "资料待补"]
            elif filter_value.get() == "初筛匹配":
                visible = [item for item in visible if item["status"] == "符合筛选"]
            for item in visible:
                status = "待调研" if item["strategy"] == "manual_lead" else item["status"]
                source = " / ".join(x for x in (item["platform"], item["market"]) if x and x != "未注明") or "来源待补"
                tree.insert("", "end", iid=item["id"], values=(item["name"], source, status), tags=("matched" if status == "符合筛选" else "pending",))
            for title, b in filter_buttons.items():
                b.configure(bg=PALE if title == filter_value.get() else WHITE, fg=ACCENT if title == filter_value.get() else MUTED)
            summary.set(f"共 {len(rows)} 款  ·  当前显示 {len(visible)} 款")
            if visible:
                empty.place_forget()
            else:
                empty_message.set("写个款名、粘贴链接，或者直接导入表格。" if not rows else "试试其他关键词，或切换到“全部”。")
                empty.place(relx=0, y=50, relwidth=1, relheight=1, height=-65)
            if chosen and tree.exists(chosen[0]):
                tree.selection_set(chosen[0])
            else:
                detail_title.set("选中一款，查看资料与下一步")
                put(detail, "清单自动保存在本机。选中商品后，可以查看来源、筛选依据并继续调研。")
                review_button.configure(state="disabled")

        def change_filter(value):
            filter_value.set(value)
            refresh()

        def remember():
            nonlocal draft
            if paste is not None and paste.winfo_exists():
                draft = content(paste)
            if len(draft.encode("utf-8")) <= 3_000_000:
                self.store.set_setting("quick_selection_draft", draft)
            return True

        def finish(screening):
            ids = selection.persist(self.store, screening)
            remember()
            search.set("")
            filter_value.set("全部")
            refresh()
            if ids:
                tree.selection_set(ids[0])
                tree.see(ids[0])
                show_selected()
            counts = screening["counts"]
            summary.set(f"已整理并保存 {len(ids)} 款  ·  初筛匹配 {counts['符合筛选']} 款")
            self.tell(f"已自动保存 {len(ids)} 款")
            self.quick_selection_last = screening

        def organize():
            try:
                finish(selection.prepare_text(content(paste), **metadata()))
                put(paste, "")
                close_intake()
            except (ValueError, OSError, csv.Error) as error:
                self.fail(error)

        def clipboard():
            try:
                value = self.clipboard_get()
            except tk.TclError:
                self.fail("剪贴板没有文字。先在 Excel 或网页里复制表格、链接或款式名称。")
                return
            try:
                finish(selection.prepare_text(value, **metadata()))
            except (ValueError, OSError, csv.Error) as error:
                self.fail(error)

        def choose_file():
            path = filedialog.askopenfilename(parent=self, filetypes=[("Excel 或选品表", "*.xlsx *.csv *.tsv *.xls")])
            if not path:
                return
            try:
                dataset = selection.read_csv(path, partial=True, **metadata())
                screening = selection.screen(dataset, selection.suggested_strategy(dataset))
                finish(screening)
                self.tell(f"已直接读取 {Path(path).name}" + (f" · {dataset['meta']['sheet']}" if dataset["meta"].get("sheet") else ""))
            except (OSError, ValueError, csv.Error) as error:
                self.fail(error)

        def selected_item():
            return self.store.get(tree.selection()[0]) if tree.selection() else None

        def show_selected(event=None):
            item = selected_item()
            if item:
                detail_title.set(item["name"][:45])
                values = [f"{selection.LABELS[k]}：{v:g}" for k, v in item["evidence"].items() if k in selection.NUMERIC and isinstance(v, (int, float))]
                put(detail, "\n".join([f"来源：{item['platform']} / {item['market']} / {item['currency']}", " · ".join(values[:5]), *item["checks"][:3], selection.STRATEGIES[item["strategy"]]["next"]]))
                review_button.configure(state="normal")

        def review():
            item = selected_item()
            if not item:
                self.fail("先在清单中选择一个想继续研究的款。")
                return
            self.store.set_setting("workflow_brief", selection.review_brief(item))
            self.store.set_setting("workflow_module", 0)
            if item["platform"] in core.PLATFORMS:
                self.store.set_setting("default_platform", item["platform"])
            if item["market"] != "未注明":
                self.store.set_setting("default_market", item["market"])
            self.show("workflows")

        def close_intake():
            nonlocal dialog, paste
            remember()
            if dialog is not None:
                dialog.grab_release()
                dialog.destroy()
            dialog, paste = None, None

        def open_intake():
            nonlocal dialog, paste
            if dialog is not None and dialog.winfo_exists():
                dialog.lift()
                return
            dialog = tk.Toplevel(self, bg=WHITE)
            dialog.title("添加选品")
            dialog.transient(self)
            dialog.geometry(f"640x590+{self.winfo_rootx() + max(20, (self.winfo_width() - 640) // 2)}+{self.winfo_rooty() + 40}")
            dialog.resizable(False, False)
            label(dialog, "添加想研究的款", 17, INK, True).pack(anchor="w", padx=24, pady=(22, 8))
            label(dialog, "款名、商品链接或表格都可以，每行一个款。", 10, MUTED).pack(anchor="w", padx=24, pady=(0, 18))
            bottom = frame(dialog)
            bottom.pack(side="bottom", fill="x", padx=24, pady=18)
            button(bottom, "整理并保存", organize, True).pack(side="right")
            button(bottom, "取消", close_intake).pack(side="right", padx=(0, 10))
            source_box = frame(dialog)
            source_box.pack(side="bottom", fill="x", padx=24)
            fields = frame(source_box)
            for i, (key, title) in enumerate((("platform", "平台"), ("market", "市场 / 站点"), ("currency", "币种"), ("date", "数据日期"))):
                fields.grid_columnconfigure(i % 2, weight=1)
                entry_field(fields, title, scope[key], row=i // 2, column=i % 2)
            expanded = tk.BooleanVar(value=False)

            def toggle_source():
                if expanded.get():
                    fields.pack(fill="x", pady=(10, 0))
                else:
                    fields.pack_forget()
            tk.Checkbutton(source_box, text="来源信息（选填）", variable=expanded, command=toggle_source, bg=WHITE,
                           activebackground=WHITE, fg=MUTED, selectcolor=WHITE, font=(FONT, 9)).pack(anchor="w")
            label(source_box, "链接先保存为线索，实时销量与价格需另补数据。", 8, MUTED).pack(anchor="w", pady=(5, 0))
            w, paste = text_area(dialog, 10)
            w.configure(highlightbackground=LINE, highlightthickness=1)
            w.pack(fill="both", expand=True, padx=24, pady=(0, 16))
            put(paste, draft)
            self.quick_selection_widgets.update(text=paste, dialog=dialog)
            dialog.protocol("WM_DELETE_WINDOW", close_intake)
            dialog.bind("<Escape>", lambda e: close_intake())
            dialog.bind("<Control-Return>", lambda e: organize())
            dialog.grab_set()
            paste.focus_set()

        search.trace_add("write", refresh)
        tree.bind("<<TreeviewSelect>>", show_selected)
        self.close_guard = remember
        self.quick_selection_widgets = dict(tree=tree, scope=scope, summary=summary, search=search,
                                            filter=filter_value, open=open_intake, empty=empty, review=review_button)
        refresh()

    def view_selection_advanced(self):
        body = self.heading("选品条件", "按数据进一步筛选", "支持 Excel、粘贴表格与 CSV。需要调整筛选条件时再使用这里。", ("返回简易选品", lambda: self.show("selection")))
        left = frame(body, WHITE, width=325)
        left.pack(side="left", fill="y", padx=(0, 18))
        left.pack_propagate(False)
        bottom_left = frame(left)
        bottom_left.pack(side="bottom", fill="x", padx=18, pady=14)
        inner, _ = scroller(left, WHITE)
        pad = frame(inner)
        pad.pack(fill="x", padx=18, pady=16)
        keys = list(selection.FILTER_KEYS)
        names = [selection.STRATEGIES[k]["name"] for k in keys]
        selected_key = self.store.setting("selection_strategy", keys[0])
        if selected_key not in keys:
            selected_key = keys[0]
        method = tk.StringVar(value=selection.STRATEGIES[selected_key]["name"])
        box, _, selector = entry_field(pad, "选择初筛思路", method, names)
        box.pack(fill="x", pady=(0, 12))
        explanation = tk.StringVar()
        label(pad, "", 9, MUTED, textvariable=explanation, wraplength=270, justify="left").pack(anchor="w", pady=(0, 14))
        rule_form = frame(pad)
        rule_form.pack(fill="x")
        parameters = {}
        self.selection_parameters = parameters
        metadata = {}
        label(pad, "导入数据的所属范围", 10, INK, True).pack(anchor="w", pady=(8, 14))
        for key, title, default, options in [
            ("platform", "数据平台", "Amazon", core.PLATFORMS), ("market", "数据市场 / 站点", "", None),
            ("currency", "数据币种（PPC 与均价须一致）", "USD", ["CNY", "USD", "EUR", "BRL", "MXN", "SGD", "MYR"]),
            ("date", "数据日期 YYYY-MM-DD", core.now()[:10], None),
        ]:
            var = tk.StringVar(value=self.store.setting("selection_" + key, default))
            box, _, _ = entry_field(pad, title, var, options)
            box.pack(fill="x", pady=(0, 12))
            metadata[key] = var
        self.selection_metadata = metadata
        label(pad, "条件是可调整的参考值。百分数字段中，\n10 表示 10%，0.1 表示 0.1%。\n修改数据日期、市场或币种后请重新导入。", 8, MUTED, justify="left").pack(anchor="w", pady=(4, 14))
        right = frame(body, BG)
        right.pack(side="left", fill="both", expand=True)
        tabs = ttk.Notebook(right)
        tabs.pack(fill="both", expand=True)
        results_page, pool_page, guide_page = [frame(tabs, BG) for _ in range(3)]
        tabs.add(results_page, text="筛选结果")
        tabs.add(pool_page, text="候选池")
        tabs.add(guide_page, text="实操与资料说明")
        summary = tk.StringVar(value="先填写数据所属市场，再导入 Excel 或表格。缺失值不会按 0 处理。")
        label(results_page, "", 9, MUTED, textvariable=summary, wraplength=660, justify="left").pack(anchor="w", pady=12)
        results_tree = self.tree(results_page, [("name", "产品 / 关键词", 260), ("status", "匹配结论", 100)])
        detail_wrap, detail = text_area(results_page, 7, True)
        detail_wrap.pack(side="bottom", before=results_tree.master, fill="x", pady=(12, 0))
        put(detail, "选中一行查看每项条件的实际值与缺项。\n\n符合筛选只表示数据满足本次条件，仍需检查目标平台需求、工厂能力、成本与预算。")
        result_actions = frame(results_page, BG)
        result_actions.pack(side="bottom", before=detail_wrap, fill="x", pady=12)
        pool_tree = self.tree(pool_page, [("name", "候选", 250), ("strategy", "思路", 130), ("review", "复核状态", 95)])
        pool_detail_wrap, pool_detail = text_area(pool_page, 7, True)
        pool_detail_wrap.pack(side="bottom", before=pool_tree.master, fill="x", pady=(12, 0))
        pool_controls = frame(pool_page, BG)
        pool_controls.pack(side="bottom", before=pool_detail_wrap, fill="x", pady=10)
        review_status = tk.StringVar(value="待复核")
        ttk.Combobox(pool_controls, textvariable=review_status, values=["待复核", "已验证", "放弃"], state="readonly", width=9).pack(side="left")
        pool_actions = frame(pool_page, BG)
        pool_actions.pack(side="bottom", before=pool_controls, fill="x", pady=(0, 10))
        guide_wrap, guide = text_area(guide_page, 24, True)
        guide_wrap.pack(fill="both", expand=True, pady=12)
        guide_path = core.ROOT / selection.GUIDE
        put(guide, guide_path.read_text(encoding="utf-8-sig") if guide_path.exists() else "实操说明文件尚未打包，请查看项目 docs/06_Selection_Practice.md。")

        def current_key():
            return keys[names.index(method.get())]

        def refresh_rules(event=None):
            for child in rule_form.winfo_children():
                child.destroy()
            parameters.clear()
            key = current_key()
            strategy = selection.STRATEGIES[key]
            explanation.set(f"{strategy['kind']}数据 · {strategy['purpose']}")
            saved = self.store.setting("selection_thresholds_" + key, {})
            for field, op, title, default in strategy["rules"]:
                var = tk.StringVar(value=str(saved.get(field + op, default)))
                box, _, _ = entry_field(rule_form, title, var)
                box.pack(fill="x", pady=(0, 12))
                parameters[field + op] = var
            if event is not None and getattr(self, "selection_dataset", None):
                filtered()

        def filtered():
            dataset = getattr(self, "selection_dataset", None)
            if not dataset:
                self.fail("请先导入一份 Excel 或选品表格。")
                return
            try:
                screening = selection.screen(dataset, current_key(), {k: v.get() for k, v in parameters.items()})
                self.selection_screening = screening
                self.store.set_setting("selection_strategy", current_key())
                self.store.set_setting("selection_thresholds_" + current_key(), screening["thresholds"])
                for item in results_tree.get_children():
                    results_tree.delete(item)
                for i, result in enumerate(screening["results"]):
                    r = result["record"]
                    results_tree.insert("", "end", iid=str(i), values=(r.get("title") or r.get("keyword") or r.get("source_id", "未命名"), result["status"]))
                counts, meta = screening["counts"], screening["meta"]
                summary.set(f"{selection.STRATEGIES[screening['strategy']]['name']} · {meta['platform']} / {meta['market']} / {meta['currency']} / {meta['date']}\n符合 {counts['符合筛选']} / 待补 {counts['资料待补']} / 不符合 {counts['不符合']} · 去重 {meta['duplicates']} 行")
                tabs.select(0)
                self.tell("条件匹配已完成，请选中候选查看依据")
            except ValueError as e:
                self.fail(e)

        def import_csv():
            path = filedialog.askopenfilename(parent=self, filetypes=[("选品导出数据", "*.xlsx *.csv *.tsv")])
            if not path:
                return
            try:
                self.selection_dataset = selection.read_csv(path, as_of=metadata["date"].get(), platform=metadata["platform"].get(), market=metadata["market"].get(), currency=metadata["currency"].get())
                for key, var in metadata.items():
                    self.store.set_setting("selection_" + key, var.get())
                filtered()
            except (OSError, ValueError, csv.Error) as e:
                self.fail(e)

        def selected_result(event=None):
            if not results_tree.selection():
                return None
            result = self.selection_screening["results"][int(results_tree.selection()[0])]
            put(detail, "\n".join([result["status"], *result["checks"], "", selection.STRATEGIES[self.selection_screening["strategy"]]["next"]]))
            return result

        def refresh_pool():
            for child in pool_tree.get_children():
                pool_tree.delete(child)
            for item in self.store.list("candidate"):
                name = selection.STRATEGIES.get(item["strategy"], {}).get("name", item["strategy"])
                pool_tree.insert("", "end", iid=item["id"], values=(item["name"], name, item["review_status"]))

        def save_candidate():
            result = selected_result()
            if not result:
                self.fail("请先在筛选结果中选择一条候选。")
                return
            item = selection.candidate(self.selection_screening, result)
            record_id = selection.candidate_id(item)
            old = self.store.get(record_id)
            if old:
                item["review_status"] = old.get("review_status", "待复核")
            self.store.save("candidate", item, record_id)
            refresh_pool()
            self.tell("已加入候选池；保留筛选依据及数据来源")

        def pool_selected(event=None):
            if not pool_tree.selection():
                return None
            item = self.store.get(pool_tree.selection()[0])
            review_status.set(item["review_status"])
            put(pool_detail, selection.review_brief(item))
            return item

        def update_review():
            chosen_status = review_status.get()
            item = pool_selected()
            if not item:
                self.fail("请先选择候选池中的一条记录。")
                return
            item["review_status"] = chosen_status
            self.store.save("candidate", item, item["id"])
            refresh_pool()
            self.tell("复核状态已保存；采购和生产仍由你决定")

        def send_to_ai():
            item = pool_selected()
            if not item:
                self.fail("请先选择候选池中的一条记录。")
                return
            self.store.set_setting("workflow_brief", selection.review_brief(item))
            self.store.set_setting("workflow_module", 0)
            self.store.set_setting("default_platform", item["platform"])
            self.store.set_setting("default_market", item["market"])
            self.show("workflows")

        def create_experiment():
            item = pool_selected()
            if not item:
                self.fail("请先选择候选池中的一条记录。")
                return
            data = dict(name="测款 · " + item["name"][:60], channel=item["platform"], date=core.now()[:10], status="计划中", budget=0, spent=0, revenue=0, hours=0,
                        goal="验证目标平台需求、样衣改进与真实利润。\n候选来源：" + item["source_id"], result="", next="填写本次人民币预算、实际成本、数量和停止条件；先核实再投入。")
            record_id = self.store.save("experiment", data)
            self.show("experiments")
            self.experiment_dialog(self.store.get(record_id))

        def export_template():
            path = filedialog.asksaveasfilename(parent=self, initialfile="选品数据模板.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if path:
                try:
                    with open(path, "w", encoding="utf-8-sig", newline="") as f:
                        csv.writer(f).writerow([aliases[0] for aliases in selection.FIELD_ALIASES.values()])
                    self.tell("空白选品模板已导出，按使用的思路填写所需列即可")
                except OSError as e:
                    self.fail(e)

        def report_text():
            if not getattr(self, "selection_screening", None):
                self.fail("请先导入并筛选数据。")
                return None
            return selection.report(self.selection_screening)

        button(bottom_left, "导入并筛选", import_csv, True).pack(fill="x", pady=(0, 8))
        button(bottom_left, "按当前条件重新筛选", filtered).pack(fill="x", pady=(0, 8))
        button(bottom_left, "下载空白选品模板", export_template).pack(fill="x")
        button(result_actions, "加入候选池", save_candidate, True).pack(side="left")
        button(result_actions, "保存报告", lambda: self.save_artifact("选品初筛", report_text(), "选品报告") if getattr(self, "selection_screening", None) else self.fail("请先筛选数据。")).pack(side="left", padx=8)
        button(result_actions, "导出报告", lambda: self.export_text(report_text(), "选品初筛报告") if getattr(self, "selection_screening", None) else self.fail("请先筛选数据。")).pack(side="right")
        button(pool_controls, "保存复核状态", update_review).pack(side="left", padx=8)
        button(pool_controls, "移除候选", lambda: self.delete_selected(pool_tree, "selection_advanced")).pack(side="right")
        button(pool_actions, "生成 AI 复核任务", send_to_ai, True).pack(side="left")
        button(pool_actions, "建立测款记录", create_experiment).pack(side="right")
        results_tree.bind("<<TreeviewSelect>>", selected_result)
        pool_tree.bind("<<TreeviewSelect>>", pool_selected)
        selector.bind("<<ComboboxSelected>>", refresh_rules)
        refresh_rules()
        refresh_pool()
        if getattr(self, "selection_dataset", None):
            filtered()
        self.selection_trees = (results_tree, pool_tree)

    def view_pricing(self):
        body = self.heading("Know your numbers", "报价与利润", "供货收入与零售售价分别测算。所有金额保持同一币种，费用按实际填写。")
        left = frame(body, BG, width=475)
        left.pack(side="left", fill="both", expand=True, padx=(0, 20))
        right = frame(body, WHITE, width=380)
        right.pack(side="left", fill="both", expand=True)
        inner, _ = scroller(left)
        inputs = frame(inner, WHITE)
        inputs.pack(fill="x")
        top = frame(inputs)
        top.pack(fill="x", padx=20, pady=(18, 0))
        get_product, product_box = self.product_selector(top)
        form = frame(inputs)
        form.pack(fill="x", padx=(20, 4))
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)
        fields = [
            ("mode", "业务模式", "供货 / 批发", ["供货 / 批发", "自营零售"]),
            ("currency", "币种", "CNY", ["CNY", "USD", "EUR", "BRL", "MXN", "SGD", "MYR", "THB"]),
            ("price", "单件收入 / 报价", "0", None), ("production", "生产 / 拿货成本", "0", None),
            ("packaging", "包装辅料 / 件", "0", None), ("inbound", "交仓 / 头程 / 件", "0", None),
            ("shipping", "配送 / 履约 / 件", "0", None), ("other", "其他成本 / 件", "0", None),
            ("loss", "售后与扣费预留 / 件", "0", None), ("commission", "佣金 / 服务费率 %", "0", None),
            ("tax", "有效税费占收入 %", "0", None), ("advertising", "广告占收入 %", "0", None),
            ("target", "目标利润率 %", "20", None), ("quantity", "测算数量 / 件", "1", None),
        ]
        variables = {}
        for i, (key, title, default, options) in enumerate(fields):
            var = tk.StringVar(value=default)
            entry_field(form, title, var, options, row=i // 2, column=i % 2)
            variables[key] = var
        label(inputs, "预留按单件金额填写；费率按收入百分比填写。\n空白按 0 处理，请核对是否漏掉实际承担的费用。", 9, MUTED, justify="left").pack(anchor="w", padx=20, pady=(0, 18))
        label(right, "测算结果", 13, INK, True).pack(anchor="w", padx=22, pady=(22, 14))
        out_wrap, out = text_area(right, 20, True)
        out_wrap.pack(fill="both", expand=True, padx=8)
        self.last_pricing = None
        self.pricing_vars = variables

        def load_product(event=None):
            p = get_product()
            if not p:
                return
            variables["production"].set(p.get("cost") or "0")
            price_key = "retail_price" if variables["mode"].get() == "自营零售" else "supply_price"
            variables["price"].set(p.get(price_key) or "0")

        def calculate():
            try:
                values = {k: v.get().strip() for k, v in variables.items()}
                result = core.calculate_pricing(values)
                self.last_pricing = core.pricing_report(values, result)
                currency = values["currency"]
                margin = "—" if result["margin"] is None else f"{result['margin']:.2f}%"
                p = get_product()
                if p:
                    self.last_pricing = f"产品：{p.get('name', '')} · 款号：{p.get('sku', '')}\n\n" + self.last_pricing
                text = (f"{p.get('name') if p else '本次测算'}  ·  {values['mode']}\n\n"
                        f"单件预计利润\n{currency}  {result['unit_profit']:,.2f}\n\n"
                        f"预计利润率                 {margin}\n"
                        f"盈亏平衡收入               {result['break_even']:,.2f}\n"
                        f"目标利润对应收入           {result['target_price']:,.2f}\n\n"
                        f"{result['quantity']} 件预计利润          {result['batch_profit']:,.2f}\n"
                        f"批量成本及损耗预留         {result['batch_cost']:,.2f}\n\n"
                        "计算说明\n单件利润 = 收入 − 比例费用 − 单件成本\n"
                        "批量成本含损耗预留，不等于首批现金垫资。\n")
                if result["unit_profit"] < 0:
                    text += "\n当前输入下预计亏损，请检查报价和成本。\n"
                if values["mode"] == "自营零售" and result["ad_roas"]:
                    text += f"\n广告前口径盈亏线 ROAS：{result['ad_roas']:.2f}\n"
                put(out, text)
                self.tell("已按当前输入计算；测算结果不代表实际结算")
            except ValueError as e:
                self.fail(e)

        product_box.bind("<<ComboboxSelected>>", load_product)
        variables["mode"].trace_add("write", lambda *_: load_product())
        button(inputs, "计算利润与报价", calculate, True).pack(fill="x", padx=20, pady=(0, 20))
        bottom = frame(right)
        bottom.pack(side="bottom", before=out_wrap, fill="x", padx=20, pady=20)
        button(bottom, "保存报告", lambda: self.save_artifact("利润测算", self.last_pricing, "利润报告")).pack(side="left")
        button(bottom, "导出", lambda: self.export_text(self.last_pricing, "利润报告")).pack(side="right")
        put(out, "填写左侧实际成本与单件收入，\n点击「计算利润与报价」。\n\n供货模式：填写你能获得的供货收入。\n零售模式：填写你收取的商品销售收入。\n\n此处没有预设任何平台的真实费率。")

    def view_workflows(self):
        body = self.heading("Seven workflows, one workspace", "AI 工作流", "带上产品资料，选择任务。可复制任务包，也可连接模型直接生成文字结果。")
        left = frame(body, WHITE, width=350)
        left.pack(side="left", fill="both", padx=(0, 18))
        left.pack_propagate(False)
        actions = frame(left)
        actions.pack(side="bottom", fill="x", padx=18, pady=(10, 18))
        form_inner, _ = scroller(left, WHITE)
        pad = frame(form_inner)
        pad.pack(fill="x", padx=18, pady=18)
        module_names = [f"{m[0]}  {m[1]}" for m in core.MODULES]
        module_index = self.store.setting("workflow_module", 2)
        module_var = tk.StringVar(value=module_names[module_index if isinstance(module_index, int) and 0 <= module_index < len(module_names) else 2])
        box, _, mod_box = entry_field(pad, "选择工作流", module_var, module_names)
        box.pack(fill="x", pady=(0, 14))
        get_product, _ = self.product_selector(pad)
        platform = tk.StringVar(value=self.store.setting("default_platform", core.PLATFORMS[0]))
        box, _, _ = entry_field(pad, "平台 / 业务模式", platform, core.PLATFORMS)
        box.pack(fill="x", pady=(0, 14))
        market = tk.StringVar(value=self.store.setting("default_market", "中国 / 供货"))
        box, _, _ = entry_field(pad, "目标市场", market)
        box.pack(fill="x", pady=(0, 14))
        label(pad, "补充资料与任务要求", 9, MUTED).pack(anchor="w")
        button(actions, "生成任务包", lambda: compose(), True).pack(fill="x", pady=(0, 8))
        self.ai_button = button(actions, "用已配置模型生成", lambda: generate())
        self.ai_button.pack(fill="x")
        label(actions, "生成会发送当前任务资料，费用按模型服务商计费。", 8, MUTED, wraplength=296, justify="left").pack(anchor="w", pady=(7, 0))
        if self.ai_running:
            self.ai_button.configure(text="模型正在生成…", state="disabled")
        small = frame(form_inner)
        small.pack(fill="x", padx=18, pady=(8, 12))
        button(small, "载入输入模板", lambda: load_template()).pack(side="left")
        button(small, "导入资料", lambda: attach()).pack(side="right")
        brief_wrap, brief = text_area(form_inner, 8)
        brief_wrap.configure(highlightbackground=LINE, highlightthickness=1)
        brief_wrap.pack(fill="x", padx=18, pady=(0, 12))
        put(brief, self.store.setting("workflow_brief", ""))
        right = frame(body, BG)
        right.pack(side="left", fill="both", expand=True)
        controls = frame(right, BG)
        controls.pack(side="bottom", fill="x", pady=(12, 4))
        notebook = ttk.Notebook(right)
        notebook.pack(fill="both", expand=True)
        prompt_wrap, prompt = text_area(notebook, 24, True)
        result_wrap, result = text_area(notebook, 24)
        notebook.add(prompt_wrap, text="任务包")
        notebook.add(result_wrap, text="文字结果 / 粘贴结果")
        put(prompt, "选择工作流并填写资料，然后点击「生成任务包」。\n\n任务包会整合产品档案、补充资料和项目提示词。\n\n没有模型接口也能使用：复制任务包到你的聊天工具，\n再把返回的内容粘贴到「文字结果」标签保存。\n\n图片和视频工作流生成制作方案与提示词，不生成成品媒体。")
        cached = self.store.setting("workflow_result", "")
        if cached:
            put(result, cached)
        self.workflow_widgets = {"prompt": prompt, "result": result, "notebook": notebook, "module": module_var}

        def index():
            return module_names.index(module_var.get())

        def compose():
            try:
                task = core.workflow_prompt(index(), get_product(), platform.get(), market.get(), content(brief))
                put(prompt, task)
                notebook.select(0)
                self.store.set_setting("workflow_brief", content(brief))
                self.store.set_setting("workflow_module", index())
                self.store.set_setting("default_platform", platform.get())
                self.store.set_setting("default_market", market.get())
                self.tell("任务包已准备，可复制或连接模型生成")
                return task
            except (OSError, ValueError) as e:
                self.fail(e)
                return None

        def generate():
            if self.ai_running:
                return
            base = self.store.setting("api_base", "")
            model = self.store.setting("api_model", "")
            if not base or not model:
                self.fail("请先到「设置与备份」填写模型接口地址和模型名称。也可以直接复制任务包使用。")
                return
            try:
                core.api_url(base)
            except ValueError as e:
                self.fail(e)
                return
            task = compose()
            if not task:
                return
            self.ai_running = True
            self.ai_button.configure(text="模型正在生成…", state="disabled")
            self.tell("模型生成中，可以切换页面；完成后会自动保存成果")
            task_name = f"{core.MODULES[index()][1]} · {(get_product() or {}).get('name', '通用任务')}"
            key = self.api_key

            def worker():
                try:
                    answer = core.call_ai(base, key, model, task)
                    self.events.put(("ai_ok", task_name, answer))
                except Exception as e:
                    self.events.put(("ai_error", str(e)))
            threading.Thread(target=worker, daemon=True).start()

        def load_template():
            if content(brief) and not messagebox.askyesno("载入模板", "替换当前补充资料为该模块的输入模板？", parent=self):
                return
            try:
                put(brief, core.workflow_template(index()))
            except OSError as e:
                self.fail(e)

        def attach():
            path = filedialog.askopenfilename(parent=self, filetypes=[("文字资料", "*.txt *.md *.csv *.json *.yaml"), ("所有文件", "*.*")])
            if not path:
                return
            try:
                if Path(path).stat().st_size > 500000:
                    raise ValueError("单次文字资料请控制在 500 KB 内。")
                text = Path(path).read_text(encoding="utf-8-sig")
                brief.insert("end", f"\n\n资料：{Path(path).name}\n{text}")
                self.tell("资料已导入；需要时点击生成任务包")
            except (OSError, UnicodeError, ValueError) as e:
                self.fail(e)

        def active():
            return content(prompt if notebook.index(notebook.select()) == 0 else result)

        button(controls, "复制当前内容", lambda: self.copy(active())).pack(side="left")
        button(controls, "保存到成果库", lambda: self.save_artifact(module_var.get(), active(), "AI任务包" if notebook.index(notebook.select()) == 0 else "文字成果")).pack(side="left", padx=8)
        button(controls, "导出文件", lambda: self.export_text(active(), module_var.get())).pack(side="right")
        button(controls, "参考案例", lambda: self.reference_view(index())).pack(side="right", padx=8)

        def remember():
            self.store.set_setting("workflow_brief", content(brief))
            self.store.set_setting("workflow_result", content(result))
            return True
        self.close_guard = remember

    def reference_view(self, index):
        window = tk.Toplevel(self)
        window.title(f"{core.MODULES[index][1]} · 项目参考资料")
        window.geometry("940x730")
        window.configure(bg=BG)
        window.transient(self)
        tabs = ttk.Notebook(window)
        tabs.pack(fill="both", expand=True, padx=16, pady=16)
        folder = core.ROOT / "Agents" / core.MODULES[index][2]
        paths = [folder / "README.md"] + sorted((folder / "examples").glob("*.md")) + [core.ROOT / "docs" / "04_Result_Checklist.md"]
        for path in paths:
            if path.is_file():
                wrap, viewer = text_area(tabs, 24, True)
                tabs.add(wrap, text="使用说明" if path.name == "README.md" else "交付检查" if path.name.startswith("04_Result") else path.stem)
                put(viewer, path.read_text(encoding="utf-8-sig"))

    def drain(self):
        try:
            while True:
                event = self.events.get_nowait()
                self.ai_running = False
                if event[0] == "ai_ok":
                    _, title, answer = event
                    self.store.save("artifact", {"name": title, "kind": "AI文字成果", "content": answer})
                    self.store.set_setting("workflow_result", answer)
                    if self.screen == "workflows":
                        put(self.workflow_widgets["result"], answer)
                        self.workflow_widgets["notebook"].select(1)
                    self.tell(f"{title}：文字结果已自动保存")
                else:
                    self.tell("生成失败，任务包仍可复制使用")
                    self.fail(event[1])
                if self.screen == "workflows":
                    self.ai_button.configure(text="用已配置模型生成", state="normal")
        except queue.Empty:
            pass
        self.after(150, self.drain)

    def view_analytics(self):
        body = self.heading("From data to decisions", "数据分析", "本地计算市场指标与广告表现。数据留在本机，报告可带入 AI 工作流继续分析。")
        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True)
        market = frame(notebook, WHITE)
        ads = frame(notebook, WHITE)
        notebook.add(market, text="市场 CSV 分析")
        notebook.add(ads, text="广告指标速算")
        toolbar = frame(market)
        toolbar.pack(fill="x", padx=20, pady=18)
        currency = tk.StringVar(value="CNY")
        ttk.Combobox(toolbar, textvariable=currency, values=["CNY", "USD", "EUR", "BRL", "MXN"], state="readonly", width=7).pack(side="left")
        market_wrap, market_out = text_area(market, 18, True)
        market_wrap.pack(fill="both", expand=True, padx=12)
        put(market_out, "导入平台或数据工具导出的 CSV / TSV 文件。\n\n必需表头：价格、月销量\n建议表头：标题、卖家、品牌\n\n支持部分中、英、葡语常见表头。所有商品金额必须同币种。\n\n样本报告用于描述这份数据，不能直接代表整个市场。")

        def import_market():
            path = filedialog.askopenfilename(parent=self, filetypes=[("市场数据", "*.csv *.tsv")])
            if not path:
                return
            try:
                if Path(path).stat().st_size > 15_000_000:
                    raise ValueError("首次分析请使用 15 MB 以内的文件。")
                report = core.market_report(path, currency.get())
                put(market_out, report)
                self.tell("市场指标已计算，可保存报告后导入市场分析工作流")
            except (OSError, ValueError, UnicodeError) as e:
                self.fail(e)

        def export_template():
            path = filedialog.asksaveasfilename(parent=self, initialfile="市场数据模板.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if path:
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as f:
                        csv.writer(f).writerow(["标题", "价格", "月销量", "卖家", "品牌"])
                    self.tell("已导出空白市场数据模板")
                except OSError as e:
                    self.fail(e)
        button(toolbar, "导入并分析", import_market, True).pack(side="left", padx=12)
        button(toolbar, "下载空白模板", export_template).pack(side="left")
        button(toolbar, "保存报告", lambda: self.save_artifact("市场指标", content(market_out), "分析报告")).pack(side="right")
        label(market, "复用原项目的数据清洗与指标脚本。价格带为数学划分，不代表选品结论。", 9, MUTED).pack(side="bottom", before=market_wrap, anchor="w", padx=22, pady=16)
        ad_left = frame(ads, WHITE, width=260)
        ad_left.pack(side="left", fill="y", padx=(16, 8), pady=16)
        ad_left.pack_propagate(False)
        ad_form, _ = scroller(ad_left, WHITE)
        variables = {}
        for i, (key, title) in enumerate([("impressions", "曝光量"), ("clicks", "点击量"), ("orders", "订单量"),
                                         ("spend", "广告花费"), ("revenue", "广告销售额"), ("unit_profit", "广告前单件贡献")]):
            box, var, _ = entry_field(ad_form, title)
            box.pack(fill="x", pady=(0, 12))
            variables[key] = var
        ad_wrap, ad_out = text_area(ads, 20, True)
        ad_wrap.pack(side="left", fill="both", expand=True, padx=(0, 15), pady=20)
        put(ad_out, "输入同一统计周期、同一币种的数据。\n\n广告前单件贡献需扣除生产、履约、佣金、税费及损耗，\n这里不再扣一次广告前成本。\n\n适用于你自主投放的业务；全托管无广告数据时可跳过。")

        def calc_ad():
            try:
                put(ad_out, core.ad_report({k: v.get() for k, v in variables.items()}))
                self.tell("广告指标已计算")
            except ValueError as e:
                self.fail(e)
        button(ad_form, "计算广告指标", calc_ad, True).pack(fill="x", pady=(6, 12))
        button(ad_form, "保存报告", lambda: self.save_artifact("广告指标", content(ad_out), "分析报告")).pack(fill="x")

    def view_experiments(self):
        body = self.heading("Small bets, clear records", "业务试验", "记录新渠道的实际收入、支出与下一步。现金收支差额不等于会计净利润。", ("+  新建试验", lambda: self.experiment_dialog()))
        month = core.now()[:7]
        records = self.store.list("experiment")
        month_records = [x for x in records if str(x.get("date", x["created"]))[:7] == month]
        spent = sum(float(x.get("spent", 0)) for x in month_records)
        revenue = sum(float(x.get("revenue", 0)) for x in month_records)
        budget = float(self.store.setting("monthly_budget", 3000))
        stats = frame(body, BG)
        stats.pack(fill="x", pady=(0, 18))
        self.card(stats, f"{month} 实际支出", f"¥ {spent:,.0f}", f"月度支出预算 ¥ {budget:,.0f}", 0, ORANGE if spent > budget else INK)
        self.card(stats, "本月实际收入", f"¥ {revenue:,.0f}", "按试验记账日期汇总", 1)
        self.card(stats, "本月现金收支差额", f"¥ {revenue - spent:,.0f}", "未计库存、应收及未支付成本", 2, ACCENT if revenue >= spent else ORANGE)
        tree = self.tree(body, [("name", "试验 / 渠道", 250), ("date", "记账日期", 110), ("budget", "预算", 90),
                               ("spent", "实际支出", 90), ("revenue", "实际收入", 90), ("status", "状态", 90)])
        for x in records:
            tree.insert("", "end", iid=x["id"], values=(x.get("name", "") + " · " + x.get("channel", ""), x.get("date", x["created"][:10]),
                x.get("budget", 0), x.get("spent", 0), x.get("revenue", 0), x.get("status", "计划中")))
        if not records:
            label(body, "还没有记录。先给一个新渠道设定验证目标，再记录实际结果。", 10, MUTED).pack(side="bottom", before=tree.master, anchor="w", pady=12)
        bottom = frame(body, BG)
        bottom.pack(side="bottom", before=tree.master, fill="x", pady=12)
        button(bottom, "查看 / 编辑", lambda: self.experiment_dialog(self.store.get(tree.selection()[0])) if tree.selection() else self.fail("请先选择一条试验。"), True).pack(side="left")
        button(bottom, "删除记录", lambda: self.delete_selected(tree, "experiments")).pack(side="left", padx=10)
        button(bottom, "导出 CSV", lambda: self.export_experiments()).pack(side="right")
        tree.bind("<Double-1>", lambda e: self.experiment_dialog(self.store.get(tree.selection()[0])) if tree.selection() else None)

    def experiment_dialog(self, record=None):
        window = tk.Toplevel(self)
        window.title("编辑业务试验" if record else "新建业务试验")
        window.geometry("660x740")
        window.configure(bg=BG)
        window.transient(self)
        window.grab_set()
        bottom = frame(window, BG)
        bottom.pack(side="bottom", fill="x", padx=24, pady=14)
        inner, _ = scroller(window)
        area = frame(inner, BG)
        area.pack(fill="both", expand=True, padx=24, pady=20)
        label(area, "用一次小试验，验证一个假设。", 17, INK, True).pack(anchor="w", pady=(0, 18))
        grid = frame(area, BG)
        grid.pack(fill="x")
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        variables = {}
        fields = [("name", "试验名称 *", "", None), ("channel", "渠道", "供货 / 批发", core.PLATFORMS),
                  ("date", "记账日期 YYYY-MM-DD", core.now()[:10], None), ("status", "状态", "计划中", ["计划中", "进行中", "已完成", "已暂停"]),
                  ("budget", "本条预算（元）", "0", None), ("spent", "实际支出（元）", "0", None),
                  ("revenue", "实际收入（元）", "0", None), ("hours", "投入时间（小时）", "0", None)]
        for i, (key, title, default, options) in enumerate(fields):
            var = tk.StringVar(value=str((record or {}).get(key, default)))
            entry_field(grid, title, var, options, row=i // 2, column=i % 2)
            variables[key] = var
        texts = {}
        for key, title in [("goal", "验证目标 / 成功标准"), ("result", "实际结果与问题"), ("next", "下一步动作")]:
            label(area, title, 9, MUTED).pack(anchor="w", pady=(6, 5))
            w, t = text_area(area, 3)
            w.pack(fill="x", pady=(0, 8))
            put(t, (record or {}).get(key, ""))
            texts[key] = t

        def save():
            try:
                data = {k: v.get().strip() for k, v in variables.items()}
                if not data["name"]:
                    raise ValueError("请填写试验名称。")
                datetime.strptime(data["date"], "%Y-%m-%d")
                if len(data["date"]) != 10:
                    raise ValueError("日期请使用 YYYY-MM-DD 格式。")
                for k in ("budget", "spent", "revenue", "hours"):
                    data[k] = float(core.number(data[k], k))
                data.update({k: content(t) for k, t in texts.items()})
                self.store.save("experiment", data, (record or {}).get("id"))
                window.destroy()
                self.show("experiments")
                self.tell("业务试验记录已保存")
            except ValueError as e:
                messagebox.showerror("请检查", str(e), parent=window)
        button(bottom, "保存试验", save, True).pack(side="right")
        button(bottom, "取消", window.destroy).pack(side="right", padx=10)

    def export_experiments(self):
        path = filedialog.asksaveasfilename(parent=self, initialfile="业务试验记录.csv", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        fields = [("name", "名称"), ("channel", "渠道"), ("date", "记账日期"), ("status", "状态"), ("budget", "预算"),
                  ("spent", "实际支出"), ("revenue", "实际收入"), ("hours", "时间"), ("goal", "目标"), ("result", "结果"), ("next", "下一步")]
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([title for _, title in fields])
                for r in self.store.list("experiment"):
                    row = [r.get(k, "") for k, _ in fields]
                    writer.writerow(["'" + str(v) if str(v).startswith(("=", "+", "-", "@", "\t", "\r")) else v for v in row])
            self.tell("业务试验已导出")
        except OSError as e:
            self.fail(e)

    def tree(self, parent, fields):
        wrap = frame(parent, WHITE)
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=[f[0] for f in fields], show="headings", selectmode="browse", height=6)
        for key, title, width in fields:
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=60, anchor="w")
        bar = ttk.Scrollbar(wrap, command=tree.yview)
        tree.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)
        return tree

    def delete_selected(self, tree, route):
        if not tree.selection():
            self.fail("请先选择一条记录。")
            return
        if messagebox.askyesno("删除记录", "确认删除这条记录？此操作不能撤销。", parent=self):
            self.store.delete(tree.selection()[0])
            self.show(route)

    def view_artifacts(self):
        body = self.heading("Keep what you create", "成果资料库", "保存任务包、模型文字结果和计算报告，随时复制、导出和继续使用。")
        split = frame(body, BG)
        split.pack(fill="both", expand=True)
        left = frame(split, BG, width=360)
        left.pack(side="left", fill="both", padx=(0, 16))
        left.pack_propagate(False)
        search = tk.StringVar()
        ttk.Entry(left, textvariable=search, font=(FONT, 10)).pack(fill="x", ipady=5, pady=(0, 12))
        tree = self.tree(left, [("name", "名称", 220), ("kind", "类型", 105)])
        right = frame(split, WHITE)
        right.pack(side="left", fill="both", expand=True)
        title_var = tk.StringVar(value="选择一份成果")
        label(right, "", 12, INK, True, textvariable=title_var).pack(anchor="w", padx=18, pady=16)
        wrap, viewer = text_area(right, 22, True)
        wrap.pack(fill="both", expand=True)
        put(viewer, "左侧选择已保存的任务包、文字成果或计算报告。\n\n生成任务包后，需要点击「保存到成果库」；\n通过模型接口生成成功的文字结果会自动保存。")
        rows = {}

        def refresh():
            rows.clear()
            for item in tree.get_children():
                tree.delete(item)
            for r in self.store.list("artifact"):
                if search.get().lower() not in (r.get("name", "") + r.get("kind", "")).lower():
                    continue
                rows[r["id"]] = r
                tree.insert("", "end", iid=r["id"], values=(r.get("name", "未命名"), r.get("kind", "")))

        def selected(event=None):
            if tree.selection():
                item = rows[tree.selection()[0]]
                title_var.set(item.get("name", "未命名"))
                put(viewer, item.get("content", ""))
        tree.bind("<<TreeviewSelect>>", selected)
        search.trace_add("write", lambda *_: refresh())
        bottom = frame(body, BG)
        bottom.pack(side="bottom", before=split, fill="x", pady=12)
        button(bottom, "复制", lambda: self.copy(content(viewer))).pack(side="left")
        button(bottom, "导出当前成果", lambda: self.export_text(content(viewer), title_var.get()), True).pack(side="left", padx=10)
        button(bottom, "删除", lambda: self.delete_selected(tree, "artifacts")).pack(side="right")
        refresh()

    def view_settings(self):
        body = self.heading("Make it yours", "设置与备份", "先使用离线工具，需要自动生成文字时再配置模型。")
        inner, _ = scroller(body)
        card = frame(inner, WHITE)
        card.pack(fill="x", pady=(0, 18))
        pad = frame(card)
        pad.pack(fill="x", padx=24, pady=22)
        label(pad, "模型连接（可选）", 14, INK, True).pack(anchor="w", pady=(0, 8))
        label(pad, "支持兼容 Chat Completions 的文字模型服务，也可连接本机模型。", 10, MUTED).pack(anchor="w", pady=(0, 18))
        variables = {}
        for key, title, default in [("api_base", "接口基础地址（例如 https://服务商域名/v1）", ""), ("api_model", "模型名称", "")]:
            var = tk.StringVar(value=self.store.setting(key, default))
            box, _, _ = entry_field(pad, title, var)
            box.pack(fill="x", pady=(0, 14))
            variables[key] = var
        key_var = tk.StringVar(value=self.api_key)
        box, _, key_widget = entry_field(pad, "API Key（本机模型可留空）", key_var)
        key_widget.configure(show="●")
        box.pack(fill="x", pady=(0, 12))
        remember = tk.BooleanVar(value=bool(self.store.setting("api_key", "")))
        tk.Checkbutton(pad, text="在当前 Windows 账户下加密保存密钥", variable=remember, bg=WHITE, fg=INK, activebackground=WHITE,
                       selectcolor=WHITE, font=(FONT, 10), anchor="w").pack(anchor="w", pady=(0, 12))
        label(pad, "密钥不写入导出备份。点击 AI 生成时，所选资料会发送给你配置的服务商。", 9, MUTED, wraplength=800, justify="left").pack(anchor="w")
        config = frame(inner, WHITE)
        config.pack(fill="x", pady=(0, 18))
        p = frame(config)
        p.pack(fill="x", padx=24, pady=22)
        label(p, "经营设置", 14, INK, True).pack(anchor="w", pady=(0, 16))
        budget_var = tk.StringVar(value=str(self.store.setting("monthly_budget", 3000)))
        box, _, _ = entry_field(p, "月度业务试验支出预算（元）", budget_var)
        box.pack(fill="x", pady=(0, 16))

        def save():
            try:
                base = variables["api_base"].get().strip()
                if base:
                    core.api_url(base)
                budget = float(core.number(budget_var.get(), "月度预算"))
                encrypted = core.protect_key(key_var.get().strip()) if remember.get() else ""
                self.api_key = key_var.get().strip()
                for key, var in variables.items():
                    self.store.set_setting(key, var.get().strip())
                self.store.set_setting("api_key", encrypted)
                self.store.set_setting("monthly_budget", budget)
                self.tell("设置已保存；未向模型发送请求")
                messagebox.showinfo("已保存", "设置已保存。你可以回到 AI 工作流生成任务。", parent=self)
            except (ValueError, OSError) as e:
                self.fail(e)
        button(p, "保存设置", save, True).pack(anchor="w")
        backup = frame(inner, WHITE)
        backup.pack(fill="x", pady=(0, 18))
        p = frame(backup)
        p.pack(fill="x", padx=24, pady=22)
        label(p, "本地数据与备份", 14, INK, True).pack(anchor="w", pady=(0, 10))
        label(p, f"数据目录：{self.store.folder}", 9, MUTED, wraplength=800, justify="left").pack(anchor="w")
        label(p, "备份包含产品、候选池、成果和试验记录。恢复时按 ID 合并，同 ID 记录会被覆盖。", 9, MUTED).pack(anchor="w", pady=(8, 16))
        buttons = frame(p)
        buttons.pack(fill="x")
        button(buttons, "导出备份", self.backup).pack(side="left")
        button(buttons, "恢复备份", self.restore).pack(side="left", padx=10)
        button(buttons, "打开数据目录", lambda: os.startfile(self.store.folder)).pack(side="left")
        label(inner, "软件不会自动上架、投广告或联系客户。平台规则与实际结算需要你在后台核对。", 9, MUTED).pack(anchor="w", pady=(4, 10))

    def backup(self):
        path = filedialog.asksaveasfilename(parent=self, initialfile=f"服装工作台备份_{core.now()[:10]}.json", defaultextension=".json", filetypes=[("JSON 备份", "*.json")])
        if path:
            try:
                self.store.backup(path)
                self.tell("备份已导出，不含模型密钥")
            except OSError as e:
                self.fail(e)

    def restore(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("JSON 备份", "*.json")])
        if not path:
            return
        if not messagebox.askyesno("恢复备份", "导入前将自动保存当前数据快照。\n同 ID 的记录会被备份覆盖，其余记录会保留。确认继续？", parent=self):
            return
        try:
            backups = self.store.folder / "backups"
            backups.mkdir(exist_ok=True)
            self.store.backup(backups / f"before_restore_{core.now().replace(':', '-')}.json")
            count = self.store.restore(path)
            self.show("settings")
            self.tell(f"已合并 {count} 条记录")
        except (OSError, ValueError, TypeError) as e:
            self.fail(e)

    def save_artifact(self, title, text, kind):
        if not text:
            self.fail("请先生成或填写内容。")
            return
        self.store.save("artifact", {"name": f"{title} · {core.now()[:16]}", "kind": kind, "content": text})
        self.tell("已保存到成果资料库")

    def export_text(self, text, title):
        if not text:
            self.fail("请先生成或填写内容。")
            return
        path = filedialog.asksaveasfilename(parent=self, initialfile=safe_name(title) + ".md", defaultextension=".md", filetypes=[("Markdown", "*.md"), ("文本", "*.txt")])
        if path:
            try:
                Path(path).write_text(text, encoding="utf-8-sig")
                self.tell(f"已导出 {Path(path).name}")
            except OSError as e:
                self.fail(e)

    def copy(self, text):
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
            self.tell("已复制到剪贴板")

    def report_callback_exception(self, exc, value, tb):
        try:
            log = self.store.folder / "error.log"
            with log.open("a", encoding="utf-8") as f:
                f.write(f"\n{core.now()}\n")
                traceback.print_exception(exc, value, tb, file=f)
        except (OSError, AttributeError):
            pass
        messagebox.showerror("操作未完成", "这次操作遇到问题，请重试。错误记录在数据目录的 error.log 中。", parent=self)

    def close(self):
        if not self.guarded():
            return
        if self.ai_running and not messagebox.askyesno("任务仍在生成", "关闭窗口会停止等待模型结果。确认退出？", parent=self):
            return
        self.store.close()
        self.destroy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    try:
        app = Workbench(args.data_dir)
        if args.smoke_test:
            errors = []

            def verify():
                try:
                    for page in ("products", "selection", "selection_advanced", "pricing", "workflows", "analytics", "experiments", "artifacts", "settings", "dashboard"):
                        app.show(page)
                        app.update_idletasks()
                    for index in range(len(core.MODULES)):
                        assert "# 项目参考流程" in core.workflow_prompt(index, {"name": "打包自检款"}, "供货 / 批发", "中国", "检查资料")
                        assert len(core.workflow_template(index)) > 100
                    sample = core.ROOT / "Agents/01_Market_Research_Agent/samples/sample_patinete_eletrico.csv"
                    assert "CNY" in core.market_report(sample)
                    assert core.calculate_pricing(dict(price=30, production=20))["unit_profit"] == 10
                    assert core.unprotect_key(core.protect_key("packaged-test")) == "packaged-test"
                    assert (core.ROOT / selection.GUIDE).is_file()
                    candidate_sample = app.store.folder / "selection-selfcheck.csv"
                    candidate_sample.write_text("ASIN,标题,月销量,评分\nSELF-CHECK,自检候选,1200,3.2\n", encoding="utf-8-sig")
                    candidate_data = selection.read_csv(candidate_sample, as_of="2026-10-16", platform="Amazon", market="US", currency="USD")
                    screening = selection.screen(candidate_data, "factory_upgrade")
                    assert screening["counts"]["符合筛选"] == 1
                    candidate_id = app.store.save("candidate", selection.candidate(screening, screening["results"][0]))
                    backup_path = app.store.folder / "selection-selfcheck.json"
                    app.store.backup(backup_path)
                    app.store.restore(backup_path)
                    assert app.store.get(candidate_id)["source_id"] == "SELF-CHECK"
                    assert len(selection.prepare_text("衬衫\n休闲裤")["results"]) == 2
                    from desktop_app import tabular
                    workbook = tabular.excel_module().Workbook()
                    workbook.active.append(["ASIN", "标题", "月销量", "评分"])
                    workbook.active.append(["XLSX-CHECK", "Excel 自检", 1200, 3.2])
                    excel_path = app.store.folder / "excel-selfcheck.xlsx"
                    workbook.save(excel_path)
                    workbook.close()
                    assert selection.read_csv(excel_path, as_of="2026-10-16", platform="Amazon", market="US", currency="USD")["records"][0]["monthly_sales"] == 1200
                    app.store.set_setting("smoke_test", "passed")
                except Exception:
                    errors.append(traceback.format_exc())
                finally:
                    app.close_guard = None
                    app.close()
            app.after(300, verify)
        app.mainloop()
        if args.smoke_test and errors:
            raise RuntimeError("\n".join(errors))
    except Exception:
        location = args.data_dir or core.default_data_dir()
        try:
            location.mkdir(parents=True, exist_ok=True)
            (location / "startup_error.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        if args.smoke_test:
            if sys.stderr:
                traceback.print_exc()
            raise SystemExit(1)
        messagebox.showerror("启动失败", f"软件未能启动。请确认软件目录可写。\n错误记录：{location / 'startup_error.log'}")


if __name__ == "__main__":
    main()
