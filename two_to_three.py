"""双文件状态 → 三文件状态：恢复 V1 DLL，并重新启用 OpenSteamTool.dll。"""

import logger
import steam_accounts

# 双文件状态的两个 DLL 改为 .orig；随后恢复这三个 .v1 文件。
DISABLE_AS_ORIG = ("dwmapi.dll", "xinput1_4.dll")
ENABLE_V1 = ("dwmapi.dll", "xinput1_4.dll", "OpenSteamTool.dll")


def run():
    """在 Steam 安装目录中执行 2 → 3 的重命名流程。"""
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("执行 2 -> 3 失败：未找到 Steam 安装目录")
        return

    logger.log("执行 2 -> 3")
    for filename in DISABLE_AS_ORIG:
        source = steam_folder / filename
        target = steam_folder / f"{filename}.orig"
        if source.exists():
            source.rename(target)
            logger.log(f"无效化：{filename} -> {filename}.orig")
        else:
            logger.log(f"不存在：{filename}")

    for filename in ENABLE_V1:
        source = steam_folder / f"{filename}.v1"
        target = steam_folder / filename
        if source.exists():
            source.rename(target)
            logger.log(f"启用：{filename}.v1 -> {filename}")
        else:
            logger.log(f"V1 版本不存在：{filename}.v1")


if __name__ == "__main__":
    run()
