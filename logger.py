"""日志模块：把程序行为写入 logs 文件夹，并自动清理过期日志。"""

import datetime  # 获取当前时间，用于日志内容、文件名和过期计算。
from pathlib import Path  # 创建、遍历 logs 文件夹。
import sys  # 判断打包后 exe 所在的目录。

import steam_accounts  # 从 settings.json 读取用户设置的日志保留天数。

# 日志跟随程序本身：打包后在 exe 同级，直接运行时在 logger.py 同级。
APP_FOLDER = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
LOG_FOLDER = APP_FOLDER / "logs"
# 日志按日期归档：同一天内的所有操作都会写入同一个日志文件。
LOG_FILE_DATE = datetime.datetime.now().strftime("%Y-%m-%d")


def clean_old_logs():
    """删除创建时间超过用户设置保留天数的 .log 文件。"""
    LOG_FOLDER.mkdir(exist_ok=True)
    now = datetime.datetime.now()
    retention_days = steam_accounts.get_log_retention_days()
    for path in LOG_FOLDER.glob("*.log"):
        created = datetime.datetime.fromtimestamp(path.stat().st_ctime)
        if (now - created).days > retention_days:
            path.unlink()


def get_log_file():
    """确保 logs 文件夹存在，并返回当天应写入的日志文件路径。"""
    LOG_FOLDER.mkdir(exist_ok=True)
    return LOG_FOLDER / f"文件替换日志_{LOG_FILE_DATE}.log"


def log(text):
    """追加一行带时分秒的文字到当天的日志文件。"""
    clean_old_logs()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_log_file().open("a", encoding="utf-8") as file:
        file.write(f"[{timestamp}] {text}\n")
