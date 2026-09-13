"""双文件状态 → 三文件状态：仅去除 DLL 的 .v1 后缀。"""

import logger
import steam_accounts

# 仅恢复三个 .v1 文件；不再创建或处理 .orig 文件。
ENABLE_V1 = ("dwmapi.dll", "xinput1_4.dll", "OpenSteamTool.dll")


def run():
    """在 Steam 安装目录中执行 2 → 3 的重命名流程。

    该操作只去除 .v1 后缀，不再无效化或修改任何 .orig 文件。
    """
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("执行 2 -> 3 失败：未找到 Steam 安装目录")
        return

    logger.log("执行 2 -> 3")
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
