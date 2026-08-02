"""程序入口：显示命令行菜单，并把 DLL、Steam、日志等功能连接起来。

本文件不直接处理 Steam 配置或 DLL 重命名，而是调用其他模块完成。
这样菜单逻辑集中在这里，新手以后增加菜单项也更容易维护。
"""

import os  # 用于调用 Windows 打开文件夹。
import shutil  # copy2() 能复制文件并尽量保留原文件的修改时间等信息。
import subprocess  # 用于调用 taskkill 强制结束 Steam 进程。
import webbrowser  # 使用系统默认浏览器打开网页。

import logger  # 写入程序运行日志。
import steam_accounts  # 读取 Steam 登录记录、保存绑定关系、启动 Steam。
import three_to_two  # 将三文件状态切换为双文件状态（禁用 GB）。
import two_to_three  # 将双文件状态切换为三文件状态（启用 GB）。

# 实际 DLL 文件名：原预演中的 ac、ab、gb 分别对应这里三个文件。
# 初始使用ac ab gb 代指3个dll文件
DWMAPI_DLL = "dwmapi.dll"
XINPUT_DLL = "xinput1_4.dll"
OPEN_STEAM_TOOL_DLL = "OpenSteamTool.dll"
# 菜单“打开网站”使用的固定网址。
WEBSITE_URL = "https://3a.lol/"
# OpenSteamTool 文件夹的基础名称；发行包可带版本后缀，例如 OpenSteamTool-1.4.8-Release (1)。
OPEN_STEAM_TOOL_FOLDER_NAME = "opensteamtool"
# 首次启动时保存 dwmapi.dll、xinput1_4.dll 原始备份的位置。
ORIGIN_DLL_COPY_FOLDER = steam_accounts.APP_FOLDER / "OrigindllCopy"


def gb_status():
    """返回给用户看的 GB 状态文字。

    这里不检查 .v1 文件；只要 OpenSteamTool.dll 存在，就表示 GB 已启用。
    """
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        return "未找到 Steam"
    return "\033[4m已启用\033[0m" if (steam_folder / OPEN_STEAM_TOOL_DLL).exists() else "\033[4m未启用\033[0m"


def get_open_steam_tool_folder():
    """自动识别程序同级的 OpenSteamTool 文件夹，并兼容版本后缀。

    优先使用名称完全等于 opensteamtool 的文件夹；没有时查找所有以该名称开头的
    文件夹。出现多个发行版本时，使用最后修改的一份，通常就是最新解压的版本。
    """
    exact_folder = steam_accounts.APP_FOLDER / OPEN_STEAM_TOOL_FOLDER_NAME
    if exact_folder.is_dir():
        return exact_folder

    candidates = [
        folder for folder in steam_accounts.APP_FOLDER.iterdir()
        if folder.is_dir() and folder.name.lower().startswith(OPEN_STEAM_TOOL_FOLDER_NAME)
    ]
    if candidates:
        return max(candidates, key=lambda folder: folder.stat().st_mtime)
    return exact_folder


def create_origin_dll_copy():
    """首次运行时备份当前的 dwmapi.dll 和 xinput1_4.dll。

    如果备份文件夹已存在，程序只补齐缺失的真实 DLL，不会覆盖已有备份。
    """
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("首次备份失败：未找到 Steam 安装目录")
        return

    ORIGIN_DLL_COPY_FOLDER.mkdir(exist_ok=True)
    for filename in (DWMAPI_DLL, XINPUT_DLL):
        source = steam_folder / filename
        backup = ORIGIN_DLL_COPY_FOLDER / filename
        # 已有真实文件备份时不覆盖，避免误替换用户最初保存的版本。
        if backup.exists():
            continue
        if source.is_file():
            shutil.copy2(source, backup)
            logger.log(f"首次备份：{filename}")
        else:
            # 文件不存在时仍创建备份文件夹，并把原因记录下来，方便排查路径问题。
            logger.log(f"首次备份失败，未找到：{filename}")


def create_manual_dll_backup():
    """创建一个新的带数字备份文件夹，并复制当前 Steam 目录中的两个 DLL。

    初始备份使用 OrigindllCopy；手动备份从 OrigindllCopy1 开始。
    程序会依次检查数字，找到第一个不存在的文件夹，因此绝不会覆盖旧备份。
    """
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("手动重新备份失败：未找到 Steam 安装目录")
        print("未找到 Steam 安装目录。")
        return

    number = 1
    while (steam_accounts.APP_FOLDER / f"OrigindllCopy{number}").exists():
        number += 1
    backup_folder = steam_accounts.APP_FOLDER / f"OrigindllCopy{number}"
    backup_folder.mkdir()
    logger.log(f"用户手动创建 DLL 备份文件夹：{backup_folder.name}")

    copied_count = 0
    for filename in (DWMAPI_DLL, XINPUT_DLL):
        source = steam_folder / filename
        if source.is_file():
            shutil.copy2(source, backup_folder / filename)
            copied_count += 1
            logger.log(f"手动备份成功：{filename} -> {backup_folder.name}")
        else:
            logger.log(f"手动备份失败，未找到：{filename}")

    print(f"已创建 {backup_folder.name}，成功备份 {copied_count} 个 DLL 文件。")


def install_open_steam_tool_v1_files():
    """将 OpenSteamTool 文件夹的三个 DLL 改为 .v1，并复制到 Steam 目录。

    操作前会检查所有文件；Steam 目录已有 .v1 目标时由用户确认是否覆盖。
    文件列表按实际项目处理：OpenSteamTool.dll、dwmapi.dll、xinput1_4.dll。
    """
    steam_folder = steam_accounts.get_steam_folder()
    open_steam_tool_folder = get_open_steam_tool_folder()
    if not steam_folder:
        logger.log("安装 OpenSteamTool V1 文件失败：未找到 Steam 安装目录")
        print("未找到 Steam 安装目录。")
        return
    if not open_steam_tool_folder.is_dir():
        logger.log(f"安装 OpenSteamTool V1 文件失败：未找到文件夹 {open_steam_tool_folder}")
        print(f"未找到 OpenSteamTool 文件夹：{open_steam_tool_folder}")
        return

    filenames = (OPEN_STEAM_TOOL_DLL, DWMAPI_DLL, XINPUT_DLL)
    existing_targets = []
    for filename in filenames:
        source = open_steam_tool_folder / filename
        source_v1 = open_steam_tool_folder / f"{filename}.v1"
        if not source.is_file():
            logger.log(f"安装 OpenSteamTool V1 文件失败：源文件不存在 {source}")
            print(f"源文件不存在：{source}")
            return
        # 源目录的 .v1 文件不能覆盖，否则会丢失该文件夹中已有的版本。
        if source_v1.exists():
            logger.log(f"安装 OpenSteamTool V1 文件取消：源目录已有 .v1 文件 {source_v1}")
            print(f"OpenSteamTool 文件夹中已有 .v1 文件，未执行：{filename}")
            return
        if (steam_folder / f"{filename}.v1").exists():
            existing_targets.append(filename)

    # Steam 目录中的旧 .v1 文件可由用户决定是否覆盖。
    if existing_targets:
        print("Steam 目录中已存在以下 .v1 文件：")
        for filename in existing_targets:
            print(f"- {filename}.v1")
        while True:
            choice = input("1. 确认覆盖  2. 取消：").strip()
            if choice == "1":
                logger.log(f"用户确认覆盖 Steam 目录的 V1 文件：{', '.join(existing_targets)}")
                break
            if choice == "2":
                logger.log(f"用户取消覆盖 Steam 目录的 V1 文件：{', '.join(existing_targets)}")
                print("已取消安装 OpenSteamTool V1 文件。")
                return
            print("请输入 1 或 2。")

    for filename in filenames:
        source = open_steam_tool_folder / filename
        source_v1 = open_steam_tool_folder / f"{filename}.v1"
        target_v1 = steam_folder / f"{filename}.v1"
        source.rename(source_v1)
        shutil.copy2(source_v1, target_v1)
        logger.log(f"安装 OpenSteamTool V1 文件：{source_v1} -> {target_v1}")
    print("OpenSteamTool 的 3 个 V1 DLL 已复制到 Steam 目录。")


def force_stop_steam():
    """调用 Windows taskkill 强制结束 steam.exe，供 Steam 卡死时使用。"""
    logger.log("用户选择菜单 7：强制结束 Steam 进程")
    result = subprocess.run(
        ["taskkill", "/F", "/IM", "steam.exe"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode == 0:
        logger.log("Steam 进程已被强制结束")
        print("Steam 进程已强制结束。")
    else:
        logger.log("未能结束 Steam 进程：可能 Steam 未运行")
        print("未发现可结束的 Steam 进程，或系统拒绝结束。")


def choose_account(slot):
    """让用户从 Steam 本机登录记录中选一个账号，作为指定槽位的绑定账号。"""
    accounts = steam_accounts.list_accounts()
    if not accounts:
        print("未找到本机 Steam 登录记录。请先打开 Steam 并至少登录一次账号。")
        return None

    # ANSI 转义码 4 表示下划线，0 表示恢复普通文字。
    # Windows 10/11 的现代终端和 PowerShell 都支持这种显示方式。
    underlined_action = (
        "\033[4m禁用SteamTool\033[0m并启动"
        if slot == "1"
        else "\033[4m启用SteamTool\033[0m并启动"
    )
    print(f"\n请选择绑定到 {underlined_action} 的 Steam 账号：")
    # enumerate(..., start=1) 让显示给用户的序号从 1 开始，更符合输入习惯。
    for index, account in enumerate(accounts, start=1):
        print(f"{index}. {account['account_name']}（{account['persona_name']}）")

    # 循环提问，直到用户输入列表中有效的数字。
    while True:
        choice = input("请输入账号序号：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            return accounts[int(choice) - 1]
        print("请输入列表中的有效序号。")


def bind_accounts():
    """依次绑定菜单 1 和菜单 2 使用的 Steam 账号，并保存到 settings.json。"""
    print("\n账号绑定")
    slot_1 = choose_account("1")
    if not slot_1:
        return None
    slot_2 = choose_account("2")
    if not slot_2:
        return None

    steam_accounts.save_bindings(slot_1, slot_2)
    logger.log(f"完成 Steam 账号绑定：账号 1 = {slot_1['account_name']}，账号 2 = {slot_2['account_name']}")
    print(f"绑定完成：1 = {slot_1['account_name']}，2 = {slot_2['account_name']}")
    return {"slot_1": slot_1, "slot_2": slot_2}


def run_file_change(enable_gb):
    """按照传入的目标状态启用或禁用 GB，而不是盲目翻转状态。

    enable_gb 为 True 时只在 GB 未启用时调用 two_to_three；
    为 False 时只在 GB 已启用时调用 three_to_two。
    """
    steam_folder = steam_accounts.get_steam_folder()
    if not steam_folder:
        logger.log("切换失败：未找到 Steam 安装目录")
        print("未找到 Steam 安装目录。")
        return

    open_steam_tool_path = steam_folder / OPEN_STEAM_TOOL_DLL
    if enable_gb:
        if open_steam_tool_path.exists():
            logger.log("OpenSteamTool.dll 已启用，无需切换")
        else:
            logger.log("启用 OpenSteamTool.dll")
            two_to_three.run()
    else:
        if open_steam_tool_path.exists():
            logger.log("禁用 OpenSteamTool.dll")
            three_to_two.run()
        else:
            logger.log("OpenSteamTool.dll 已禁用，无需切换")


def run_bound_account(bindings, slot, enable_gb):
    """先处理 GB 状态，再使用对应绑定账号启动 Steam。"""
    binding = bindings[f"slot_{slot}"]
    logger.log(f"用户选择菜单 {slot}：准备启动 Steam 账号 {binding['account_name']}")
    run_file_change(enable_gb)
    try:
        steam_accounts.start_account(binding)
        logger.log(f"已向 Steam 发送启动账号请求：{binding['account_name']}")
        print(f"正在启动 Steam 账号：{binding['account_name']}")
    except FileNotFoundError as error:
        # 未安装 Steam 时只提示错误，菜单程序不会因此崩溃。
        print(error)


def run_switch():
    """菜单 3 的旧式切换功能：根据当前状态切换到相反状态。"""
    logger.log("用户选择菜单 3：自动切换 GB 状态")
    steam_folder = steam_accounts.get_steam_folder()
    enable_gb = bool(steam_folder) and not (steam_folder / OPEN_STEAM_TOOL_DLL).exists()
    run_file_change(enable_gb=enable_gb)


def open_folder(folder, description):
    """用 Windows 资源管理器打开文件夹；找不到时显示清楚的路径提示。"""
    if not folder.is_dir():
        logger.log(f"打开{description}失败，文件夹不存在：{folder}")
        print(f"未找到{description}文件夹：{folder}")
        return
    logger.log(f"用户打开{description}文件夹：{folder}")
    os.startfile(str(folder))


def settings(bindings):
    """显示设置子菜单，并在用户选择返回时把最新绑定信息交还给主菜单。"""
    while True:
        print("\n设置")
        print("1. 更换1、2的启动账号绑定")
        print(f"2. 修改日志保留时间（当前：{steam_accounts.get_log_retention_days()} 天）")
        print("3. 打开原始 DLL 备份")
        print("4. 手动重新备份（请手动删除旧备份）")
        print("5. 安装 OpenSteamTool 文件到 Steam")
        print("6. 返回上一级")
        choice = input("请输入选项：").strip()

        if choice == "1":
            # 换绑失败（例如没有 Steam 登录记录）时，保留原来的 bindings。
            logger.log("用户在设置中选择：换绑 Steam 账号")
            bindings = bind_accounts() or bindings
        elif choice == "2":
            value = input("请输入日志保留天数：").strip()
            if value.isdigit() and int(value) > 0:
                steam_accounts.set_log_retention_days(int(value))
                # 修改保留时间后立刻清理一次已经过期的日志。
                logger.clean_old_logs()
                logger.log(f"用户修改日志保留时间为：{value} 天")
                print("日志保留时间已更新。")
            else:
                print("请输入大于 0 的整数。")
        elif choice == "3":
            open_folder(ORIGIN_DLL_COPY_FOLDER, "原始 DLL 备份")
        elif choice == "4":
            create_manual_dll_backup()
        elif choice == "5":
            install_open_steam_tool_v1_files()
        elif choice == "6":
            logger.log("用户从设置返回主菜单")
            return bindings
        else:
            print("无效选项。")


def main():
    """程序主循环：完成首次备份、首次绑定，并持续响应用户的菜单输入。"""
    logger.log("程序已打开")
    create_origin_dll_copy()
    # 没有 settings.json 或绑定数据不完整时，首次启动会进入账号绑定流程。
    bindings = steam_accounts.load_bindings() or bind_accounts()

    while True:
        print(f"\nopensteamtool：{gb_status()}")
        print(f"1. 禁用steamtool并启动 {bindings['slot_1']['persona_name']}" if bindings else "1. 禁用steamtool并启动账号 1（未绑定）")
        print(f"2. 启用steamtool并启动 {bindings['slot_2']['persona_name']}" if bindings else "2. 启用steamtool并启动账号 2（未绑定）")
        print("3. 切换steamtool状态")
        print("4. 打开3A社区")
        print("5. 打开游戏清单lua文件夹")
        print("6. 打开OpenSteamTool")
        print("7. 强制结束 Steam 进程")
        print("8. 设置")

        choice = input("请输入选项：").strip()
        if choice in ("1", "2"):
            if not bindings:
                print("请先在设置中完成账号绑定。")
            else:
                run_bound_account(bindings, int(choice), enable_gb=(choice == "2"))
        elif choice == "3":
            run_switch()
        elif choice == "4":
            logger.log(f"用户选择菜单 4：打开网站 {WEBSITE_URL}")
            webbrowser.open(WEBSITE_URL)
        elif choice == "5":
            logger.log("用户选择菜单 5：打开 Steam 游戏清单文件夹")
            # 游戏清单位于 Steam 安装目录，而不是本程序目录。
            steam_folder = steam_accounts.get_steam_folder()
            if steam_folder:
                open_folder(steam_folder / "config" / "lua", "游戏清单")
            else:
                logger.log("打开 Steam 游戏清单失败：未找到 Steam 安装目录")
                print("未找到 Steam 安装目录。")
        elif choice == "6":
            logger.log("用户选择菜单 6：打开 OpenSteamTool 文件夹")
            open_folder(get_open_steam_tool_folder(), "OpenSteamTool")
        elif choice == "7":
            force_stop_steam()
        elif choice == "8":
            logger.log("用户选择菜单 8：进入设置")
            bindings = settings(bindings)
        else:
            print("无效选项。")


# 只有直接运行 main.py（或运行打包 exe）时才启动菜单；被其他文件 import 时不执行。
if __name__ == "__main__":
    main()
