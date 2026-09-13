"""OpenSteamTool 图形界面入口。"""
import os
import subprocess
import sys
import time
import webbrowser
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import re
from pathlib import Path
from urllib.request import Request, urlopen
from html import unescape
from urllib.parse import quote

PROCESS_STARTED = time.perf_counter()

import logger
import steam_accounts
import three_to_two
import two_to_three

OPEN_STEAM_TOOL_DLL = "OpenSteamTool.dll"
WEBSITE_URL = "https://3a.lol/"
GITHUB_URL = "https://github.com/OpenSteam001/OpenSteamTool"
MANIFEST_REPOSITORY = "Jelly-fresh/ManifestHub2copy"


class StartupTimer:
    """记录启动各阶段耗时，便于定位启动瓶颈。"""
    def __init__(self):
        self.started = PROCESS_STARTED
        self.last = self.started
        self.steps = []

    def mark(self, name):
        current = time.perf_counter()
        self.steps.append((name, current - self.last))
        self.last = current

    def report(self):
        total = time.perf_counter() - self.started
        details = "，".join(f"{name}={elapsed * 1000:.1f}ms" for name, elapsed in self.steps)
        return f"[启动耗时] 总计={total * 1000:.1f}ms；{details}"


def app_icon_path():
    resource_folder = Path(getattr(sys, "_MEIPASS", steam_accounts.APP_FOLDER))
    return resource_folder / "app.ico"

def tool_folder():
    exact = steam_accounts.APP_FOLDER / "opensteamtool"
    if exact.is_dir(): return exact
    choices = [p for p in steam_accounts.APP_FOLDER.iterdir() if p.is_dir() and p.name.lower().startswith("opensteamtool")]
    return max(choices, key=lambda p: p.stat().st_mtime) if choices else exact


class App(tk.Tk):
    def __init__(self):
        startup = StartupTimer()
        startup.mark("导入模块")
        super().__init__()
        startup.mark("创建 Tk 窗口")
        self.title("OpenSteamTool 管理器")
        self.iconbitmap(app_icon_path())
        self.geometry("550x420"); self.minsize(500, 415)
        startup.mark("设置窗口")
        self.bindings = steam_accounts.load_bindings()
        startup.mark("加载账号绑定")
        self.build()
        startup.mark("构建界面")
        self.refresh()
        startup.mark("刷新界面")
        startup_report = startup.report()
        print(startup_report)
        logger.log(f"程序已打开（GUI）；{startup_report}")

    def build(self):
        box = ttk.Frame(self, padding=22); box.pack(fill="both", expand=True)
        footer = ttk.Frame(box); footer.pack(side="bottom", fill="x")
        project_link = tk.Label(footer, text="项目地址", foreground="#0563c1", cursor="hand2", font=("Microsoft YaHei UI", 9, "underline"))
        project_link.pack(anchor="e")
        project_link.bind("<Button-1>", lambda event: webbrowser.open("https://github.com/Jelly-fresh/switch-opensteamtool"))
        ttk.Label(box, text="OpenSteamTool 管理器", font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        self.status = ttk.Label(box, font=("Microsoft YaHei UI", 11)); self.status.pack(anchor="w", pady=(8, 16))
        self.one = ttk.Button(box, command=lambda: self.launch("slot_1", False)); self.one.pack(fill="x", pady=3)
        self.two = ttk.Button(box, command=lambda: self.launch("slot_2", True)); self.two.pack(fill="x", pady=3)
        controls = ttk.Frame(box); controls.pack(fill="x", pady=14)
        items = [
            ("切换 OpenSteamTool 状态", self.switch, 0, 0),
            ("打开游戏清单文件夹", self.open_depotcache, 0, 1),
            ("打开 OpenSteamTool", lambda: self.open_folder(tool_folder(), "OpenSteamTool"), 4, 0),
            ("打开 OpenSteamTool 网站", lambda: webbrowser.open(GITHUB_URL), 1, 0),
            ("打开lua文件夹", self.open_lua, 1, 1),
            # 下面的直接改，gui界面也是，直接改后面的数字，横，竖）
            ("打开 3A 社区", lambda: webbrowser.open(WEBSITE_URL), 2, 0),
            ("校对游戏版本", self.check_game_version, 2, 1),
            ("强制结束 Steam", self.stop, 3, 1),
            ("设置", self.settings, 4, 1),
        ]
        for label, cmd, row, column in items:
            ttk.Button(controls, text=label, command=cmd).grid(row=row, column=column, sticky="ew", padx=3, pady=4)
        self.custom_site = ttk.Frame(controls)
        self.custom_site.grid(row=3, column=0, sticky="ew", padx=3, pady=4)
        self.custom_site.columnconfigure(0, weight=1)
        # 右侧的 ⓘ 会占用一小段宽度；padding=(增加左侧内边距使主按钮文字仍以整组按钮为视觉中心。
        self.custom_site_button = ttk.Button(self.custom_site, command=self.open_custom_website, padding=(35, 0, 0, 0))
        self.custom_site_button.grid(row=0, column=0, sticky="ew")
        ttk.Button(self.custom_site, text="ⓘ", width=3, command=self.edit_custom_website).grid(row=0, column=1)
        controls.columnconfigure((0, 1), weight=1)
        self.note = ttk.Label(box, foreground="#28783c", wraplength=500); self.note.pack(anchor="w", pady=12)

    def popup(self, title):
        """创建使用应用图标、并相对主窗口居中的普通弹窗。"""
        window = tk.Toplevel(self)
        window.title(title)
        window.iconbitmap(app_icon_path())
        self.update_idletasks()
        window.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - window.winfo_reqwidth()) // 2)
        y = self.winfo_rooty() + max(0, (self.winfo_height() - window.winfo_reqheight()) // 2)
        window.geometry(f"+{x}+{y}")
        return window

    def refresh(self):
        steam = steam_accounts.get_steam_folder(); enabled = bool(steam and (steam / OPEN_STEAM_TOOL_DLL).exists())
        if steam:
            state_text, color = ("已启用", "#d43c3c") if enabled else ("未启用", "#258a42")
            self.status.config(text=f"OpenSteamTool 状态：{state_text}", foreground=color)
        else:
            self.status.config(text="OpenSteamTool 安装目录：未找到", foreground="#333333")
        a = self.bindings.get("slot_1", {}).get("persona_name", "未绑定") if self.bindings else "未绑定"
        b = self.bindings.get("slot_2", {}).get("persona_name", "未绑定") if self.bindings else "未绑定"
        self.one.config(text=f"禁用 OpenSteamTool 并启动：{a}"); self.two.config(text=f"启用 OpenSteamTool 并启动：{b}")
        self.custom_site_button.config(text=steam_accounts.get_custom_website()[0])

    def notify(self, text): self.note.config(text=text); self.refresh()
    def state(self, enable):
        steam = steam_accounts.get_steam_folder()
        if not steam: raise FileNotFoundError("未找到 Steam 安装目录。")
        active = (steam / OPEN_STEAM_TOOL_DLL).exists()
        if enable and not active: two_to_three.run()
        elif not enable and active: three_to_two.run()

    def launch(self, slot, enable):
        if not self.bindings or slot not in self.bindings:
            messagebox.showwarning("尚未绑定", "请先在“设置”中绑定 Steam 账号。", parent=self); return
        try:
            self.state(enable); steam_accounts.start_account(self.bindings[slot]); self.notify(f"正在启动 Steam 账号：{self.bindings[slot]['account_name']}")
        except FileNotFoundError as e: messagebox.showerror("操作失败", str(e), parent=self)

    def switch(self):
        steam = steam_accounts.get_steam_folder()
        try: self.state(not bool(steam and (steam / OPEN_STEAM_TOOL_DLL).exists())); self.notify("OpenSteamTool 状态已切换。")
        except FileNotFoundError as e: messagebox.showerror("操作失败", str(e), parent=self)

    def open_folder(self, folder, desc):
        if not folder.is_dir(): messagebox.showerror("未找到文件夹", f"未找到{desc}文件夹：\n{folder}", parent=self)
        else: os.startfile(str(folder))
    def open_lua(self):
        steam = steam_accounts.get_steam_folder()
        if steam: self.open_folder(steam / "config" / "lua", "游戏清单")
        else: messagebox.showerror("操作失败", "未找到 Steam 安装目录。", parent=self)
    def open_depotcache(self):
        steam = steam_accounts.get_steam_folder()
        if steam: self.open_folder(steam / "depotcache", "游戏清单 2")
        else: messagebox.showerror("操作失败", "未找到 Steam 安装目录。", parent=self)
    @staticmethod
    def find_version_files(folder, number):
        """查找文件名中编号前 N−1 位相同的文件，允许最后一位不同。"""
        prefix = number[:-1]
        if not folder.is_dir():
            return []
        try:
            return [path for path in folder.rglob("*") if path.is_file() and any(token.startswith(prefix) for token in re.findall(r"\d+", path.name))]
        except OSError:
            return []
    @staticmethod
    def find_github_version_files(number, repository=MANIFEST_REPOSITORY):
        """从公开 GitHub 分支网页读取该游戏编号对应的文件。"""
        headers = {"User-Agent": "OpenSteamTool-Manager"}
        try:
            page_url = f"https://github.com/{repository}/tree/{number}"
            with urlopen(Request(page_url, headers=headers), timeout=15) as response:
                page = response.read().decode("utf-8", errors="replace")
            pattern = rf'href="/{re.escape(repository)}/blob/{re.escape(number)}/([^"?#]+)"'
            paths = list(dict.fromkeys(unescape(item) for item in re.findall(pattern, page)))
            return ([(path, number) for path in paths], None)
        except OSError as error:
            return [], str(error)
    def check_game_version(self):
        steam = steam_accounts.get_steam_folder()
        if not steam:
            messagebox.showerror("操作失败", "未找到 Steam 安装目录。", parent=self); return
        dialog = self.popup("校对游戏版本")
        # 下面的几行设置弹窗大小、最小尺寸、模态化，并创建主框架和顶部输入行。
        dialog.geometry("560x470"); dialog.minsize(500, 400)
        dialog.transient(self)
        main = ttk.Frame(dialog, padding=18); main.pack(fill="both", expand=True)
        top = ttk.Frame(main); top.pack(fill="x")
        ttk.Label(top, text="游戏编号：").pack(side="left")
        number = tk.StringVar()
        entry = ttk.Entry(top, textvariable=number, width=28); entry.pack(side="left")
        note = ttk.Label(main, text="按编号前 N−1 位搜索，输入编号的最后一位可与文件名不同。选择文件，双击打开文件夹。", foreground="#666")
        note.pack(anchor="w", pady=(7, 10))
        lists = []
        # 两个本地列表框分别显示 lua 文件夹和 depotcache 文件夹的搜索结果。2 4 分别表示列表框的高度（显示行数）。
        for title, rows in (("lua 文件夹搜索结果", 2), ("depotcache 文件夹搜索结果", 4)):
            group = ttk.LabelFrame(main, text=title, padding=7); group.pack(fill="x", pady=4)
            scrollbar = ttk.Scrollbar(group, orient="vertical")
            view = tk.Listbox(group, height=rows, activestyle="none", yscrollcommand=scrollbar.set)
            scrollbar.config(command=view.yview)
            view.pack(side="left", fill="x", expand=True); scrollbar.pack(side="left", fill="y")
            actions = ttk.Frame(group); actions.pack(side="left", fill="y", padx=(7, 0))
            ttk.Button(actions, text="删\n除", width=2, command=lambda i=len(lists): delete_local(i)).pack(expand=True)
            lists.append((view, []))
        repository = steam_accounts.get_manifest_repository()
        github_group = ttk.LabelFrame(main, text=f"GitHub 仓库搜索结果（{repository}）", padding=7)
        github_group.pack(fill="x", pady=4)
        github_scrollbar = ttk.Scrollbar(github_group, orient="vertical")
        # height 6 ， 显示 6 行，
        github_view = tk.Listbox(github_group, height=6, activestyle="none", yscrollcommand=github_scrollbar.set)
        github_scrollbar.config(command=github_view.yview)
        github_view.pack(side="left", fill="x", expand=True); github_scrollbar.pack(side="left", fill="y")
        github_actions = ttk.Frame(github_group)
        github_actions.pack(side="left", fill="y", padx=(7, 0))
        github_paths = []
        def selected_path(index):
            view, paths = lists[index]
            selected = view.curselection()
            return paths[selected[0]] if selected and selected[0] < len(paths) else None
        def delete_local(index):
            path = selected_path(index)
            if not path:
                messagebox.showwarning("未选择文件", "请先选择要删除的文件。", parent=dialog)
                return
            try:
                path.unlink()
            except OSError as error:
                messagebox.showerror("删除失败", f"无法删除文件：\n{error}", parent=dialog)
                return
            logger.log(f"删除版本文件：{path}")
            refresh_local(index)

        def refresh_local(index):
            folder = (steam / "config" / "lua", steam / "depotcache")[index]
            view, _ = lists[index]
            paths = self.find_version_files(folder, number.get().strip())
            lists[index] = (view, paths)
            view.delete(0, tk.END)
            for path in paths:
                view.insert(tk.END, str(path))
            if not paths:
                view.insert(tk.END, "未找到匹配文件")

        def open_file(index):
            path = selected_path(index)
            if path: os.startfile(str(path.parent))
        for index, (view, _) in enumerate(lists):
            view.bind("<Double-Button-1>", lambda event, i=index: open_file(i))
        def github_selected():
            selected = github_view.curselection()
            return github_paths[selected[0]] if selected and selected[0] < len(github_paths) else None
        def open_github_folder(event=None):
            selected = github_selected()
            if selected:
                path, branch = selected
                folder = path.rsplit("/", 1)[0] if "/" in path else ""
                webbrowser.open(f"https://github.com/{repository}/tree/{branch}/{folder}".rstrip("/"))
        github_view.bind("<Double-Button-1>", open_github_folder)

        def import_github_file():
            selected = github_selected()
            if not selected:
                messagebox.showwarning("未选择文件", "请先选择要导入的 GitHub 文件。", parent=dialog)
                return
            path, branch = selected
            suffix = Path(path).suffix.lower()
            if suffix not in (".lua", ".manifest"):
                messagebox.showinfo("无法导入", "只支持导入 .lua 文件和 .manifest 文件。", parent=dialog)
                return
            target_folder = steam / "config" / "lua" if suffix == ".lua" else steam / "depotcache"
            target = target_folder / Path(path).name
            raw_url = f"https://raw.githubusercontent.com/{repository}/{quote(branch, safe='')}/{quote(path, safe='/')}"
            try:
                target_folder.mkdir(parents=True, exist_ok=True)
                with urlopen(Request(raw_url, headers={"User-Agent": "OpenSteamTool-Manager"}), timeout=15) as response:
                    target.write_bytes(response.read())
            except (OSError, ValueError) as error:
                messagebox.showerror("导入失败", f"无法下载文件：\n{error}", parent=dialog)
                return
            logger.log(f"导入并替换版本文件：{target}")
            refresh_local(0 if suffix == ".lua" else 1)
            messagebox.showinfo("导入完成", f"文件已导入并替换：\n{target}", parent=dialog)

        ttk.Button(github_actions, text="导\n入", width=2, command=import_github_file).pack(expand=True)
        def verify():
            value = number.get().strip()
            if not value.isdigit() or len(value) < 2:
                messagebox.showwarning("输入无效", "请输入有效数字。", parent=dialog); return
            if steam_accounts.get_open_steamdb():
                webbrowser.open(f"https://steamdb.info/app/{value}/depots/?branch=public")
            folders = (steam / "config" / "lua", steam / "depotcache")
            for index, folder in enumerate(folders):
                number.set(value)
                refresh_local(index)
            nonlocal github_paths, repository
            repository = steam_accounts.get_manifest_repository()
            github_paths, github_error = self.find_github_version_files(value, repository)
            github_view.delete(0, tk.END)
            for path, _ in github_paths: github_view.insert(tk.END, path)
            if not github_paths:
                github_view.insert(tk.END, f"GitHub 读取失败：{github_error}" if github_error else "未找到匹配分支或文件")
        ttk.Button(top, text="校验", command=verify).pack(side="left", padx=8)
        entry.bind("<Return>", lambda event: verify()); entry.focus_set()
    def open_custom_website(self):
        label, url = steam_accounts.get_custom_website()
        if not url.startswith(("https://", "http://")):
            messagebox.showerror("网址无效", "请通过右侧 ⓘ 按钮设置以 http:// 或 https:// 开头的网址。", parent=self)
            return
        webbrowser.open(url)
    def edit_custom_website(self):
        label, url = steam_accounts.get_custom_website()
        dialog = self.popup("编辑自定义网站")
        dialog.transient(self); dialog.grab_set(); dialog.resizable(False, False)
        form = ttk.Frame(dialog, padding=20); form.pack(fill="both", expand=True)
        ttk.Label(form, text="按钮显示文字：").grid(row=0, column=0, sticky="w", pady=(0, 8))
        label_value = tk.StringVar(value=label)
        label_entry = ttk.Entry(form, textvariable=label_value, width=38)
        label_entry.grid(row=0, column=1, pady=(0, 8))
        ttk.Label(form, text="目标网址：").grid(row=1, column=0, sticky="w")
        url_value = tk.StringVar(value=url)
        ttk.Entry(form, textvariable=url_value, width=38).grid(row=1, column=1)
        ttk.Label(form, text="网址须以 https:// 或 http:// 开头。", foreground="#666").grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 12))
        buttons = ttk.Frame(form); buttons.grid(row=3, column=0, columnspan=2, sticky="e")
        def save():
            new_label, new_url = label_value.get().strip(), url_value.get().strip()
            if not new_label or not new_url.startswith(("https://", "http://")):
                messagebox.showerror("输入无效", "请填写按钮文字，以及以 http:// 或 https:// 开头的网址。", parent=dialog)
                return
            steam_accounts.set_custom_website(new_label, new_url)
            dialog.destroy(); self.notify("自定义网站已保存。")
        ttk.Button(buttons, text="取消", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="保存", command=save).pack(side="right", padx=(0, 6))
        label_entry.focus_set()
    def stop(self):
        result = subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True, text=True, errors="replace")
        if result.returncode == 0: self.notify("Steam 进程已强制结束。")
        else: messagebox.showinfo("提示", "未发现可结束的 Steam 进程，或系统拒绝结束。", parent=self)

    def bind_accounts(self):
        accounts = steam_accounts.list_accounts()
        if not accounts: messagebox.showwarning("未找到账号", "请先打开 Steam 并至少登录一次账号。", parent=self); return
        win = self.popup("绑定 Steam 账号"); win.transient(self); win.grab_set()
        labels = [f"{x['account_name']}（{x['persona_name']}）" for x in accounts]; values = [tk.StringVar(value=labels[0]), tk.StringVar(value=labels[0])]
        for title, value in zip(("禁用 OpenSteamTool 后启动：", "启用 OpenSteamTool 后启动："), values):
            row = ttk.Frame(win, padding=(18, 10)); row.pack(fill="x"); ttk.Label(row, text=title).pack(side="left"); ttk.Combobox(row, textvariable=value, values=labels, state="readonly", width=28).pack(side="left")
        def save():
            steam_accounts.save_bindings(accounts[labels.index(values[0].get())], accounts[labels.index(values[1].get())]); self.bindings = steam_accounts.load_bindings(); win.destroy(); self.notify("账号绑定已保存。")
        ttk.Button(win, text="保存绑定", command=save).pack(pady=12)

    def settings(self):
        win = self.popup("设置"); box = ttk.Frame(win, padding=20); box.pack()
        ttk.Button(box, text="更换启动账号绑定", command=self.bind_accounts).pack(fill="x", pady=3)
        repository = tk.StringVar(value=steam_accounts.get_manifest_repository())
        repository_row = ttk.Frame(box); repository_row.pack(fill="x", pady=3)
        ttk.Label(repository_row, text="GitHub 仓库：").pack(side="left")
        ttk.Entry(repository_row, textvariable=repository, width=28).pack(side="left", fill="x", expand=True)
        def save_repository():
            value = repository.get().strip()
            if not re.fullmatch(r"[^/\\\s]+/[^/\\\s]+", value):
                messagebox.showerror("仓库格式无效", "请输入 GitHub 仓库格式：所有者/仓库名。", parent=win)
                return
            steam_accounts.set_manifest_repository(value)
            self.notify("GitHub 搜索仓库已更新。")
        ttk.Button(repository_row, text="保存", command=save_repository).pack(side="left", padx=(6, 0))
        def days():
            value = simpledialog.askinteger("日志保留时间", "请输入日志保留天数：", parent=win, minvalue=1)
            if value: steam_accounts.set_log_retention_days(value); logger.clean_old_logs(); self.notify("日志保留时间已更新。")
        ttk.Button(box, text=f"修改日志保留时间（当前 {steam_accounts.get_log_retention_days()} 天）", command=days).pack(fill="x", pady=3)
        startup = tk.BooleanVar(value=steam_accounts.get_startup_enabled())
        def toggle_startup():
            try:
                steam_accounts.set_startup_enabled(startup.get())
                self.notify("已开启开机自启动。" if startup.get() else "已关闭开机自启动。")
            except OSError as error:
                startup.set(steam_accounts.get_startup_enabled())
                messagebox.showerror("设置失败", f"无法修改开机自启动设置：\n{error}", parent=win)
        ttk.Checkbutton(box, text="开机时自动启动管理器", variable=startup, command=toggle_startup).pack(anchor="w", pady=8)
        open_steamdb = tk.BooleanVar(value=steam_accounts.get_open_steamdb())
        def toggle_steamdb():
            steam_accounts.set_open_steamdb(open_steamdb.get())
            self.notify("已开启校验时自动弹出 SteamDB。" if open_steamdb.get() else "已关闭校验时自动弹出 SteamDB。")
        ttk.Checkbutton(box, text="校验版本时自动弹出 SteamDB", variable=open_steamdb, command=toggle_steamdb).pack(anchor="w", pady=8)


if __name__ == "__main__": App().mainloop()
