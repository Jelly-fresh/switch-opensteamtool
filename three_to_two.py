"""三文件状态 → 双文件状态：禁用 OpenSteamTool.dll，并启用两个原始 DLL。"""

import logger
import steam_accounts

# 原预演名称 ac、ab、gb 对应的实际 DLL 名称。
DISABLE_AS_V1 = ("dwmapi.dll", "xinput1_4.dll", "OpenSteamTool.dll")
ENABLE_ORIG = ("dwmapi.dll", "xinput1_4.dll")


def run():
    """在 Steam 安装目录中执行 3 → 2 的重命名流程。"""
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("执行 3 -> 2 失败：未找到 Steam 安装目录")
        return

    logger.log("执行 3 -> 2")
    for filename in DISABLE_AS_V1:
        source = steam_folder / filename
        target = steam_folder / f"{filename}.v1"
        if source.exists():
            source.rename(target)
            logger.log(f"无效化：{filename} -> {filename}.v1")
        else:
            logger.log(f"不存在：{filename}")

    for filename in ENABLE_ORIG:
        source = steam_folder / f"{filename}.orig"
        target = steam_folder / filename
        if source.exists():
            source.rename(target)
            logger.log(f"启用：{filename}.orig -> {filename}")
        else:
            logger.log(f"原始版本不存在：{filename}.orig")


if __name__ == "__main__":
    run()
