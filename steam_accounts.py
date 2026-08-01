"""Steam 相关工具：定位 Steam、读取登录记录、保存账号绑定、启动账号。

本模块只读取 Steam 的 loginusers.vdf 登录记录，不读取、更不会保存密码。
账号绑定和日志设置保存在本程序目录的 settings.json 中。
"""

import json  # 把 Python 字典保存为 settings.json，以及从中读取设置。
import os  # 读取 Windows 的 ProgramFiles 环境变量。
from pathlib import Path  # 更安全、直观地处理文件夹和文件路径。
import re  # 使用正则表达式从 VDF 文本中找账号字段。
import subprocess  # 启动 steam.exe 并传入 -login 参数。
import sys  # 判断当前是直接运行 .py 还是打包后的 .exe。

# 打包为 exe 后，sys.executable 是 exe 的路径；直接运行时则使用本文件所在目录。
APP_FOLDER = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
# 所有可修改的用户设置都放在这里，便于备份或重置。
SETTINGS_FILE = APP_FOLDER / "settings.json"


def _steam_folder():
    """查找 Steam 安装目录。

    首先读取 Steam 写入 Windows 注册表的安装路径；若没有注册表信息，
    再检查 Program Files 常见安装位置。函数名前的下划线表示仅供本模块内部使用。
    """
    try:
        import winreg  # winreg 是 Python 自带的 Windows 注册表访问模块。

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            path, _ = winreg.QueryValueEx(key, "SteamPath")
            if path:
                return Path(path)
    except (FileNotFoundError, OSError):
        # 未安装 Steam 或注册表键不存在时，继续使用下面的备用查找方式。
        pass

    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            candidate = Path(base) / "Steam"
            if (candidate / "steam.exe").exists():
                return candidate
    return None


def get_steam_folder():
    """提供给 main.py 使用的公开接口：找到 Steam 文件夹时返回 Path，否则返回 None。"""
    return _steam_folder()


def _read_text(path):
    """尝试使用 Steam 配置可能使用的编码读取文本，避免中文昵称出现乱码。"""
    for encoding in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # 极少数异常编码下仍尽量读取内容，并用替换字符代替无法识别的字符。
    return path.read_text(errors="replace")


def _user_blocks(text):
    """从 loginusers.vdf 文本中逐个取出“SteamID + 对应大括号内容”。

    VDF 使用大括号表示层级。这里通过 depth 计数来找到与开始大括号对应的结束大括号。
    """
    for match in re.finditer(r'"(\d{16,20})"\s*\{', text):
        start = match.end()
        depth = 1
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    yield match.group(1), text[start:index]
                    break


def list_accounts():
    """返回本机 Steam 保存过的账号列表。

    每个账号包含 SteamID、登录名 AccountName、显示昵称 PersonaName。
    这些信息来自 loginusers.vdf，列表中不含任何密码。
    """
    folder = _steam_folder()
    login_users = folder / "config" / "loginusers.vdf" if folder else None
    if not login_users or not login_users.exists():
        return []

    accounts = []
    for steam_id, block in _user_blocks(_read_text(login_users)):
        account = re.search(r'"AccountName"\s*"([^"]+)"', block)
        persona = re.search(r'"PersonaName"\s*"([^"]+)"', block)
        if account:
            accounts.append({
                "steam_id": steam_id,
                "account_name": account.group(1),
                # 有些记录没有昵称，这种情况用登录名代替显示。
                "persona_name": persona.group(1) if persona else account.group(1),
            })
    return accounts


def _load_settings():
    """读取 settings.json；文件不存在、内容损坏时返回空字典，保证程序能继续运行。"""
    if not SETTINGS_FILE.exists():
        return {}
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(data):
    """把设置字典以易阅读的缩进 JSON 格式写入文件。"""
    SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_bindings():
    """读取两个菜单账号的绑定信息；两个槽位都存在才认为绑定有效。"""
    data = _load_settings()
    return data if "slot_1" in data and "slot_2" in data else None


def save_bindings(slot_1, slot_2):
    """保存账号 1、账号 2 绑定，同时保留日志保留时间等其他设置。"""
    data = _load_settings()
    data.update({"slot_1": slot_1, "slot_2": slot_2})
    _save_settings(data)


def get_log_retention_days():
    """读取日志保留天数；未设置或值不正确时使用默认的 120 天。"""
    value = _load_settings().get("log_retention_days", 120)
    return value if isinstance(value, int) and value > 0 else 120


def set_log_retention_days(days):
    """更新日志保留天数，并且不影响已经保存的 Steam 账号绑定。"""
    data = _load_settings()
    data["log_retention_days"] = days
    _save_settings(data)


def find_bound_account(binding):
    """根据已绑定的 SteamID 在当前本机登录记录中查找账号；找不到则返回 None。"""
    return next((item for item in list_accounts() if item["steam_id"] == binding.get("steam_id")), None)


def start_account(binding):
    """启动 Steam 并请求使用指定登录名。

    -login 只把登录名交给 Steam；密码和 Steam Guard 验证始终由 Steam 客户端自行处理。
    """
    folder = _steam_folder()
    if not folder or not (folder / "steam.exe").exists():
        raise FileNotFoundError("未找到 Steam 安装目录")
    subprocess.Popen([str(folder / "steam.exe"), "-login", binding["account_name"]])
