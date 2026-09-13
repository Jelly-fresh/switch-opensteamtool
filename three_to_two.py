"""三文件状态 → 双文件状态：仅将当前 DLL 改为 .v1。"""

import logger
import steam_accounts

# 三个当前启用的 DLL 都改名为 .v1；不再处理 .orig 文件。
DISABLE_AS_V1 = ("dwmapi.dll", "xinput1_4.dll", "OpenSteamTool.dll")


def run():
    """在 Steam 安装目录中执行 3 → 2 的重命名流程。

    该操作只添加 .v1 后缀，不再恢复或修改任何 .orig 文件。
    """
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

if __name__ == "__main__":
    run()
