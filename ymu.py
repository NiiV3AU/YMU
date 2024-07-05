import win32gui
from win10toast import ToastNotifier
import sys

notif = ToastNotifier()

def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

if getattr(sys, 'frozen', False):
    # check if YMU is already running. If it is, bring it to foreground and exit (moving this above the rest of the imports makes it much faster).
    ymu_window = win32gui.FindWindow(None, 'YMU - YimMenuUpdater')
    if ymu_window is not None and ymu_window != 0:
        win32gui.SetForegroundWindow(ymu_window)
        # try:
        #     notif.show_toast('YMU', 'The program is already running!', duration = 10, icon_path = (resource_path("assets\\icon\\ymu.ico")))
        # except TypeError: #win10Toast has a bug and will always raise a TypeError. It's not a big deal so it's safe to just simply ignore it.
        #     pass
        sys.exit(0)
    else:
        # if YMU is not already running, show a splash screen during the loading time.
        import pyi_splash

# Libraries YMU depends on
import customtkinter as ctk
import hashlib
import os
import psutil
import requests
import subprocess
import webbrowser
import winreg
from bs4 import BeautifulSoup
from customtkinter import CTkFont
from pyinjector import inject
from threading import Thread
from PIL import Image
from time import sleep
import json
from configparser import ConfigParser

# YMU Appearance
CONFIGPATH = "ymu\\config.ini"


def create_or_read_config():
    config = ConfigParser()
    if os.path.isfile(CONFIGPATH):
        config.read(CONFIGPATH)
        theme = config["ymu"]["theme"]
        ctk.set_appearance_mode(theme)
    else:
        if os.path.exists("ymu"):
            pass
        else:
            os.makedirs("ymu")
        with open(CONFIGPATH, 'w') as configfile:
            config.add_section("ymu")
            config.set("ymu", "theme", "dark")
            config.write(configfile)


create_or_read_config()


# Colors
BG_COLOR = ("#cccccc", "#333333")
BG_COLOR_D = ("#e4e4e4", "#272727")  # BG_COLOR_D = "#2b2b2b"
GREEN = ("#16b145", "#45e876")
GREEN_D = ("#7dcb95", "#3c8e55")  # GREEN_D = "#36543F"
GREEN_B = "#36543F"
WHITE = ("#272727", "#DCE4EE")
RED = ("#b11625", "#e84555")
RED_D = ("#cb7d85", "#8e3c44")
YELLOW = ("#b19216", "#e8c745")
# BLUE = "#4596e8"


folder_white = ctk.CTkImage(
    dark_image=Image.open(resource_path("assets\\img\\fo_normal.png")),
    light_image=Image.open(resource_path("assets\\img\\fo_normal_l.png")),
    size=(24, 24)
)

folder_hvr = ctk.CTkImage(
    dark_image=Image.open(resource_path("assets\\img\\fo_hover.png")),
    light_image=Image.open(resource_path("assets\\img\\fo_hover_l.png")),
    size=(24, 24)
)


# YMU root - title - minsize - launch size - launch in center of sreen
root = ctk.CTk()
root.title("YMU - YimMenuUpdater")
root.resizable(False, False)
root.iconbitmap(resource_path("assets\\icon\\ymu.ico"))
root.configure(fg_color=BG_COLOR_D)
width_of_window = 400
height_of_window = 420
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()
x_coordinate = (screen_width / 2) - (width_of_window / 2)
y_coordinate = (screen_height / 2) - (height_of_window / 2)
root.geometry(
    "%dx%d+%d+%d" % (width_of_window, height_of_window, x_coordinate, y_coordinate)
)

# Fonts
BIG_FONT = CTkFont(family="Manrope", size=16, weight="bold")
SMALL_FONT = CTkFont(family="Manrope", size=12)
SMALL_BOLD_FONT = CTkFont(family="Manrope", size=13, weight="bold")
SMALL_BOLD_FONT_U = CTkFont(family="Manrope", size=13, weight="bold", underline=True)
BOLD_FONT = CTkFont(family="Manrope", size=14, weight="bold")
TOOLTIP_FONT = CTkFont(family="Manrope", size=12, slant="italic")
CODE_FONT = CTkFont(family="JetBrains Mono", size=12)
CODE_FONT_U = CTkFont(family="JetBrains Mono", size=12, underline=True)
CODE_FONT_BIG = CTkFont(family="JetBrains Mono", size=16)
CODE_FONT_SMALL = CTkFont(family="JetBrains Mono", size=10)

# Version, Url and Paths
LOCAL_VER = "v1.0.7"
DLLURL = "https://github.com/YimMenu/YimMenu/releases/download/nightly/YimMenu.dll"
DLLDIR = ".\\ymu\\dll"
LOCALDLL = ".\\ymu\\dll\\YimMenu.dll"

LAUNCHERS = ["Select Launcher", # placeholder
             "Steam", 
             "Epic Games",
             "Rockstar Games",
            ]

launcherVar = ctk.StringVar()

def set_launcher(launcher:str):
    launcherVar.set(launcher)

# self update stuff

# delete the updater on init
if os.path.isfile("./ymu_self_updater.exe"):
    os.remove("./ymu_self_updater.exe")

# get YMU's remote version:
ymu_update_message = ctk.StringVar()

def get_ymu_ver():
    try:
        r = requests.get("https://github.com/NiiV3AU/YMU/tags")
        soup = BeautifulSoup(r.content, "html.parser")
        result = soup.find(class_="Link--primary Link")
        s = str(result)
        result = s.replace("</a>", "")
        charLength = len(result)
        latest_version = result[charLength - 6:]
        return latest_version

    except Exception:
        update_response.pack(pady=5, padx=0, expand=False, fill=None, anchor="s")
        ymu_update_message.set(
            "❌ Failed to get the latest Github version.\nCheck your Internet connection and try again."
        )
        update_response.configure(text_color=YELLOW)
        sleep(5)
        ymu_update_message.set("")
        ymu_update_button.configure(state="normal")
        update_response.pack_forget()


def check_for_ymu_update():
    ymu_update_button.configure(state="disabled")
    YMU_VERSION = get_ymu_ver()
    global update_available
    try:
        if LOCAL_VER < YMU_VERSION:
            update_response.pack(pady=5, padx=0, expand=False, fill=None, anchor="s")
            ymu_update_message.set(f"Update {YMU_VERSION} is available.")
            update_response.configure(text_color=GREEN)
            ymu_update_button.configure(state="normal", text="Update YMU")
            update_available = True
            change_update_button()
            sleep(3)
            update_response.pack_forget()

        elif LOCAL_VER == YMU_VERSION:
            update_response.pack(pady=5, padx=0, expand=False, fill=None, anchor="s")
            ymu_update_message.set("YMU is up-to-date ✅")
            update_response.configure(text_color=WHITE)
            update_available = False
            sleep(3)
            ymu_update_message.set("")
            ymu_update_button.configure(state="normal")
            update_response.pack_forget()

        elif LOCAL_VER > YMU_VERSION:
            update_response.pack(pady=5, padx=0, expand=False, fill=None, anchor="s")
            ymu_update_message.set(
                "⚠️ Invalid version detected ⚠️\nPlease download YMU from\nthe official Github repository."
            )
            update_response.configure(text_color=RED)
            ymu_update_button.configure(state="normal", text="Open Github")
            change_update_button()
            sleep(5)
            update_response.pack_forget()

    except Exception:
        pass


def download_self_updater():
    response = requests.get(
        "https://github.com/xesdoog/YMU-Updater/releases/download/latest/ymu_self_updater.exe"
    )
    if response.status_code == 200:
        with open("ymu_self_updater.exe", "wb") as file:
            file.write(response.content)
            return "OK"
    else:
        return "Error"


def launch_ymu_update():
    global start_self_update
    try:
        ymu_update_message.set("Downloading self updater...")
        update_response.configure(text_color=WHITE)
        ymu_update_button.configure(state="disabled")
        if download_self_updater() == "OK":
            ymu_update_message.set("YMU will now close to apply the updates")
            sleep(3)
            start_self_update = True
            root.destroy()
        else:
            ymu_update_message.set("❌ Failed to download self updater!")
            update_response.configure(text_color=RED)
            sleep(5)
            ymu_update_message.set("")
            update_response.configure(text_color=WHITE)
            ymu_update_button.configure(state="normal", text="Update YMU")

    except Exception:
        pass


def start_update_thread():
    Thread(target=launch_ymu_update, daemon=True).start()


def open_github_release():
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU/releases/latest")


def change_update_button():
    if update_available:
        ymu_update_button.configure(command=start_update_thread)
    else:
        ymu_update_button.configure(command=open_github_release)


def ymu_update_thread():
    ymu_update_message.set("Please wait...")
    Thread(target=check_for_ymu_update, daemon=True).start()


# scrapes the release/build SHA256 of the latest YimMenu release
def get_remote_sha256():
    try:
        r = requests.get("https://github.com/YimMenu/YimMenu/releases/latest")
        soup = BeautifulSoup(r.content, "html.parser")
        list = soup.find(class_="notranslate")
        l = list("code")
        s = str(l)
        tag = s.replace("[<code>", "")
        sep = " "
        head, sep, _ = tag.partition(sep)
        REM_SHA = head
        REM_SHA_LENG = len(REM_SHA)
        if REM_SHA_LENG == 64:
            return REM_SHA
    except requests.exceptions.ConnectionError as e:
        progress_prcnt_label.configure(text=f'Error while trying to\nconnect to "GitHub.com"\nERROR: {e}',text_color=RED)
        reset_progress_prcnt_label(5)


# self explanatory
def check_if_dll_is_downloaded():
    while True:
        if os.path.exists(DLLDIR):
            if os.path.isfile(LOCALDLL):
                LOCAL_SHA = get_local_sha256()
                REM_SHA = get_remote_sha256()
                if LOCAL_SHA == REM_SHA:
                    return "Update"
                else:
                    return "Update"
            else:
                return "Download"
        else:
            return "Download"


# Find GTAV's process and update the 'inject' tab
def find_gta_process():
    global pid  # <- I know it's a bad habit but if it works why fix it? 😂 (true 🤙 - "never change a running system")
    global is_running
    for p in psutil.process_iter(["name", "exe", "cmdline"]):
        if (
            "GTA5.exe" == p.info["name"]
            or p.info["exe"]
            and os.path.basename(p.info["exe"]) == "GTA5.exe"
            or p.info["cmdline"]
            and p.info["cmdline"][0] == "GTA5.exe"
        ):
            pid = p.pid
            is_running = True
            sleep(0.5)
            break
        else:
            pid = 0
            is_running = False


def process_search_thread():
    Thread(target=find_gta_process, daemon=True).start()


# run it once to initialize 'pid' and 'is_running'
process_search_thread()


# reads/calculates the SHA256 of local (downloaded) version of YimMenu
def get_local_sha256():
    if os.path.exists(LOCALDLL):
        sha256_hash = hashlib.sha256()
        with open(LOCALDLL, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    else:
        return None


def refresh_download_button():

    if get_remote_sha256() == get_local_sha256():
        download_button.configure(state="disabled")
        progress_prcnt_label.configure(
            text="YimMenu is up to date.", text_color=WHITE
        )
        progressbar.set(1.0)

    else:
        download_button.configure(state="normal")
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} available!", text_color=GREEN
        )
        progressbar.set(0)
        try:
            notif.show_toast('YMU', f'A new YimMenu release is out! Get the latest version from the {check_if_dll_is_downloaded()} tab.', duration = 15, icon_path = (resource_path("assets\\icon\\ymu.ico")))
        except TypeError:
            pass


# downloads the dll from github and displays progress in a progressbar
def download_dll():
    reset_progress_prcnt_label(0)
    if not os.path.exists(DLLDIR):
        os.makedirs(DLLDIR)
    try:
        with requests.get(DLLURL, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            progressbar.set(0)
            downloaded_size = 0
            with open(LOCALDLL, "wb") as f:
                for chunk in r.iter_content(chunk_size=131072):  # 128 KB chunks (in binary)
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = downloaded_size / total_size
                    progressbar.set(progress)
                    progress_prcnt_label.configure(
                        text=f"Progress: {int(progress*100)}%"
                    )
                    progress_prcnt_label.update_idletasks()  # refresh widget
        # if download successful
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} successful", text_color=GREEN
        )
        sleep(5)
        check_if_dll_is_downloaded()
        if not os.path.exists(LOCALDLL):
            progress_prcnt_label.configure(
                text="File was removed!\nMake sure to either turn off your antivirus or add YMU folder to exceptions.",
                text_color=RED,
            )
            sleep(5)
        Thread(target=refresh_download_button, daemon=True).start()

    # if download failed
    except requests.exceptions.RequestException as e:
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} error: {e}", text_color=RED
        )
        reset_progress_prcnt_label(3)


# starts the download in a thread to keep the gui responsive
def start_download():
    download_button.configure(state="disabled")
    Thread(target=download_dll, daemon=True).start()


# Injects YimMenu into GTA5.exe process
def inject_yimmenu():
    try:
        inject_button.configure(state="disabled")
        inject_progress_label.configure(
            text="🔍 Searching for GTA5 process...",
            text_color=WHITE,
        )
        dummy_progress(injection_progressbar)
        process_search_thread()
        sleep(1)  # give it time to update the values
        injection_progressbar.set(0)
        if pid != 0:
            if os.path.isfile(LOCALDLL):
                inject_progress_label.configure(
                    text=f"Found process 'GTA5.exe' with PID: [{pid}]",
                    text_color=GREEN,
                )
                sleep(2)
                inject_progress_label.configure(
                    text="💉 Injecting...", text_color=GREEN
                )
                dummy_progress(injection_progressbar)
                inject(pid, LOCALDLL)
                sleep(2)
                inject_progress_label.configure(
                    text=f"Successfully injected YimMenu.dll into GTA5.exe",
                    text_color=GREEN,
                )
                sleep(3)
                injection_progressbar.set(0)
                process_search_thread()
                sleep(
                    5
                )  # Wait for 5 seconds and check if the game crashes on injection.
                if is_running:
                    inject_progress_label.configure(
                        text="Have fun!",
                        text_color=GREEN,
                    )
                    sleep(
                        5
                    )  # exit the app after successful injection. If the game crashes, the program continues to run
                    root.destroy()  # if you don't want this behavior feel free to remove it. I just thought it would be nice to free some resources for people with potato PCs.
                else:
                    inject_progress_label.configure(
                        text="Uh Oh! Did your game crash?",
                        text_color=RED,
                    )
                reset_inject_progress_label(10)

            else:
                inject_progress_label.configure(
                    text="YimMenu.dll not found! Download the latest release\nand make sure your anti-virus is not interfering.",
                    text_color=RED,
                )
                reset_inject_progress_label(5)

        else:
            inject_progress_label.configure(text="GTA5.exe not found! Please start the game.", text_color=RED)
            reset_inject_progress_label(5)

        inject_button.configure(state="normal")

    except Exception:
        injection_progressbar.set(0)
        inject_progress_label.configure(
            text="Failed to inject YimMenu!",
            text_color=RED,
        )
        reset_inject_progress_label(5)
        inject_button.configure(state="normal")


def start_injection():
    Thread(target=inject_yimmenu, daemon=True).start()


def dummy_progress(widget):
    for i in range(0, 11):
        i += 0.01
        widget.set(i / 10)
        sleep(0.05)


def reset_inject_progress_label(n):
    sleep(n)
    inject_progress_label.configure(text="Progress: N/A", text_color=WHITE)
    injection_progressbar.set(0)


# opens github repo
def open_github(e):
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU")


# label for github repo - author (NV3) - version
copyright_label = ctk.CTkLabel(
    master=root,
    font=CODE_FONT_SMALL,
    text_color=BG_COLOR_D,
    text="↣ Click Here for GitHub Repo ↢\n⋉ © NV3 ⋊\n{" + f"{LOCAL_VER}" + "}",
    bg_color="transparent",
    fg_color=BG_COLOR_D,
    justify="center",
)
copyright_label.pack(pady=10, fill=None, expand=False, anchor="n", side="top")

copyright_label.bind("<ButtonRelease>", open_github)


# basic ahh animation for copyright_label
def copyright_label_ani_master():
    try:
        while True:
            if appearance_mode_optionemenu.get() == "Dark":
                copyright_label.configure(text_color="#4D4D4D")
                sleep(0.1)
                copyright_label.configure(text_color="#666666")
                sleep(0.1)
                copyright_label.configure(text_color="#808080")
                sleep(0.1)
                copyright_label.configure(text_color="#999999")
                sleep(0.1)
                copyright_label.configure(text_color="#B3B3B3")
                sleep(0.1)
                copyright_label.configure(text_color="#CCCCCC")
                sleep(0.2)
                copyright_label.configure(text_color="#E6E6E6")
                sleep(0.3)
                copyright_label.configure(text_color="#FFFFFF")
                sleep(0.4)
                copyright_label.configure(text_color="#E6E6E6")
                sleep(0.3)
                copyright_label.configure(text_color="#CCCCCC")
                sleep(0.2)
                copyright_label.configure(text_color="#B3B3B3")
                sleep(0.1)
                copyright_label.configure(text_color="#999999")
                sleep(0.1)
                copyright_label.configure(text_color="#808080")
                sleep(0.1)
                copyright_label.configure(text_color="#666666")
                sleep(0.1)

            elif appearance_mode_optionemenu.get() == "Light":
                # copyright_label.configure(text_color="#4D4D4D")
                # sleep(0.1)
                # copyright_label.configure(text_color="#ffffff")
                # sleep(0.1)
                # copyright_label.configure(text_color="#dbdbdb")
                sleep(0.1)
                copyright_label.configure(text_color="#b7b7b7")
                sleep(0.1)
                copyright_label.configure(text_color="#939393")
                sleep(0.2)
                copyright_label.configure(text_color="#6f6f6f")
                sleep(0.2)
                copyright_label.configure(text_color="#4b4b4b")
                sleep(0.3)
                copyright_label.configure(text_color="#272727")
                sleep(0.4)
                copyright_label.configure(text_color="#4b4b4b")
                sleep(0.3)
                copyright_label.configure(text_color="#6f6f6f")
                sleep(0.2)
                copyright_label.configure(text_color="#939393")
                sleep(0.2)
                copyright_label.configure(text_color="#b7b7b7")
                sleep(0.1)
                copyright_label.configure(text_color="#dbdbdb")

    except Exception:
        pass


# starts all animations - currently only copyright
def master_ani_start():
    Thread(target=copyright_label_ani_master, daemon=True).start()


root.after(1000, master_ani_start)

# def tabview_border_ani():
#     while True:
#         sleep(0.2)
#         tabview.configure(border_color=GREEN_D)
#         sleep(0.2)
#         tabview.configure(border_color="#3ea55d")
#         sleep(0.2)        
#         tabview.configure(border_color="#41bb66")
#         sleep(0.2)
#         tabview.configure(border_color="#43d26e")
#         sleep(0.2)
#         tabview.configure(border_color=GREEN)
#         sleep(0.2)
#         tabview.configure(border_color="#43d26e")
#         sleep(0.2)
#         tabview.configure(border_color="#41bb66")
#         sleep(0.2)
#         tabview.configure(border_color="#3ea55d")


# Download and SHA256 tabs
tabview = ctk.CTkTabview(
    master=root,
    fg_color=BG_COLOR,
    bg_color="transparent",
    corner_radius=12,
    segmented_button_fg_color=BG_COLOR,
    segmented_button_selected_color=BG_COLOR_D,
    segmented_button_selected_hover_color=BG_COLOR,
    segmented_button_unselected_color=BG_COLOR,
    segmented_button_unselected_hover_color=BG_COLOR_D,
    text_color=GREEN, border_color=GREEN_D, border_width=2
)
tabview.pack(pady=10, padx=10, expand=True, fill="both")


# Thread(target=tabview_border_ani, daemon=True).start()
def refresh_download_tab():
    if check_if_dll_is_downloaded() == "Download":
        tabview.add("Download")
    else:
        tabview.add("Update")


refresh_download_tab()


tabview.add("Inject")
tabview.add("Settings Ξ")


# reset progress label
def reset_progress_prcnt_label(n):
    sleep(n)
    progress_prcnt_label.configure(text="Progress: N/A", text_color=WHITE)
    progressbar.set(0)


progressbar = ctk.CTkProgressBar(
    master=tabview.tab(check_if_dll_is_downloaded()),
    orientation="horizontal",
    height=8,
    corner_radius=14,
    fg_color=BG_COLOR_D,
    progress_color=GREEN,
    width=140,
)
progressbar.pack(pady=5, padx=5, expand=False, fill="x", side="bottom", anchor="s")
progressbar.set(0)


progress_prcnt_label = ctk.CTkLabel(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text="",
    font=CODE_FONT_SMALL,
    height=10,
    text_color=WHITE,
)
progress_prcnt_label.pack(
    pady=5, padx=5, expand=False, fill=None, anchor="s", side="bottom"
)


def hover_download_button(e):
    download_button.configure(text_color=GREEN, fg_color=GREEN_B)
    tabview.configure(border_color=GREEN)


def nohover_download_button(e):
    download_button.configure(text_color=BG_COLOR_D, fg_color=GREEN)
    tabview.configure(border_color=GREEN_D)


# more info for Download
def open_download_info(e):
    download_info = ctk.CTkToplevel(fg_color=BG_COLOR_D)
    download_info.title("Download Info")
    download_info.minsize(300, 220)
    download_info.resizable(False, False)
    width_of_window = 300
    height_of_window = 220
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coordinate = (screen_width / 2) - (width_of_window / 2)
    y_coordinate = (screen_height / 2) - (height_of_window / 2)
    download_info.geometry(
        "%dx%d+%d+%d" % (width_of_window, height_of_window, x_coordinate, y_coordinate)
    )

    def di_frame_hover(e):
        download_info_frame.configure(border_color=GREEN)

    def di_frame_normal(e):
        download_info_frame.configure(border_color=GREEN_D)

    download_info_frame = ctk.CTkFrame(master=download_info, fg_color=BG_COLOR, border_width=1, border_color=GREEN_D)
    download_info_frame.pack(pady=10,padx=10, expand=True, fill="both")
    download_info_label = ctk.CTkLabel(
        master=download_info_frame,
        text=f'⭐ {check_if_dll_is_downloaded()} YimMenu.dll ⭐\n\nHow-To:\n↦ Click on ({check_if_dll_is_downloaded()})\n↪ Wait for the download to finish\n↪ file in "YMU/dll"-folder\n\nIf the file gets deleted,\nadd an exception in\nyour antivirus or\ndisable it.',
        font=CODE_FONT,
        justify="center",
        text_color=GREEN,
    )
    download_info_label.pack(pady=10, padx=10, expand=True, fill="both")
    download_info.bind("<Enter>", di_frame_hover)
    download_info.bind("<Leave>", di_frame_normal)
    download_info.attributes("-topmost", "true")


def hover_download_mi(e):
    download_more_info_label.configure(
        text="Click here for more info",
        cursor="hand2",
        text_color=GREEN,
        font=CODE_FONT_U,
    )
    tabview.configure(border_color=GREEN)


def normal_download_mi(e):
    download_more_info_label.configure(
        text="↣ Click here for more info ↢",
        cursor="arrow",
        text_color=WHITE,
        font=CODE_FONT,
    )
    tabview.configure(border_color=GREEN_D)


download_more_info_label = ctk.CTkLabel(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text="↣ Click here for more info ↢",
    justify="center",
    font=CODE_FONT,
)
download_more_info_label.pack(pady=10, padx=10, expand=False, fill=None)


download_more_info_label.bind("<ButtonRelease>", open_download_info)
download_more_info_label.bind("<Enter>", hover_download_mi)
download_more_info_label.bind("<Leave>", normal_download_mi)


# Changelog
def open_changelog(e):
    changelog = ctk.CTkToplevel(fg_color=BG_COLOR_D)
    changelog.title("YimMenu Changelog")
    width_of_window = 640
    height_of_window = 640
    changelog.minsize(400, 400)
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coordinate = (screen_width / 2) - (width_of_window / 2)
    y_coordinate = (screen_height / 2) - (height_of_window / 2)
    changelog.geometry("%dx%d+%d+%d" % (width_of_window, height_of_window, x_coordinate, y_coordinate))

    def border_frame_hover(e):
        border_frame.configure(border_color=GREEN)
        changelog_frame.configure(label_text_color=GREEN)

    def border_frame_normal(e):
        border_frame.configure(border_color=GREEN_D)
        changelog_frame.configure(label_text_color=GREEN_D)

    border_frame = ctk.CTkFrame(master=changelog, fg_color=BG_COLOR, border_width=1, border_color=GREEN_D, corner_radius=10)
    border_frame.pack(pady=10, padx=10, expand=True, fill="both")

    changelog_frame = ctk.CTkScrollableFrame(
        master=border_frame,
        corner_radius=0,
        scrollbar_button_color=GREEN_B,
        scrollbar_button_hover_color=GREEN_D,
        scrollbar_fg_color=BG_COLOR,
        label_font=BOLD_FONT,
        label_text="YimMenu - Changelog:",
        label_text_color=GREEN,
        label_fg_color=BG_COLOR,
        fg_color=BG_COLOR,
    )
    changelog_frame.pack(pady=10, padx=10, expand=True, fill="both")
    changelog_frame.bind("<Enter>", border_frame_hover)
    changelog_frame.bind("<Leave>", border_frame_normal)

    r = requests.get("https://yim.gta.menu/changelog.html")
    soup = BeautifulSoup(r.content, "html.parser")
    changelog_hmtl = soup.find(class_="card").get_text()
    changelog_label = ctk.CTkLabel(
        master=changelog_frame,
        font=CODE_FONT,
        fg_color=BG_COLOR,
        text_color=WHITE,
        justify="center",
        wraplength=600,
    )
    changelog_label.configure(text=changelog_hmtl)
    changelog_label.pack(expand=True, fill="both", pady=0, padx=0)

    def open_changelog_ib():
        webbrowser.open_new_tab("https://yim.gta.menu/changelog.html")

    def oib_hover(e):
        open_in_browser_button.configure(text="Open in Browser ↗", font=CODE_FONT_U, text_color=GREEN)

    def oib_normal(e):
        open_in_browser_button.configure(text="↣ Open in Browser ↢", font=CODE_FONT, text_color=WHITE)

    open_in_browser_button = ctk.CTkButton(master=changelog, text="↣ Open in Browser ↢", fg_color=BG_COLOR_D, hover_color=BG_COLOR_D, text_color=WHITE, font=CODE_FONT, command=open_changelog_ib)
    open_in_browser_button.pack(pady=0,padx=0,expand=False, fill=None)
    open_in_browser_button.bind("<Enter>", oib_hover)
    open_in_browser_button.bind("<Leave>", oib_normal)
    changelog.attributes("-topmost", "true")


def hover_changelog_l(e):
    changelog_l.configure(
        text="Click here for Changelog",
        cursor="hand2",
        text_color=GREEN,
        font=CODE_FONT_U,
    )
    tabview.configure(border_color=GREEN)


def normal_changelog_l(e):
    changelog_l.configure(
        text="↣ Click here for Changelog ↢",
        cursor="arrow",
        text_color=WHITE,
        font=CODE_FONT,
    )
    tabview.configure(border_color=GREEN_D)


changelog_l = ctk.CTkLabel(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text="↣ Click here for Changelog ↢",
    justify="center",
    font=CODE_FONT, text_color=WHITE
)
changelog_l.pack(pady=10, padx=10, expand=False, fill=None)


changelog_l.bind("<ButtonRelease>", open_changelog)
changelog_l.bind("<Enter>", hover_changelog_l)
changelog_l.bind("<Leave>", normal_changelog_l)


download_button = ctk.CTkButton(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text=f"{check_if_dll_is_downloaded()}",
    command=start_download,
    fg_color=GREEN,
    hover_color=GREEN_D,
    text_color=BG_COLOR_D,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)
download_button.pack(
    pady=10,
    padx=5,
    expand=True,
    fill=None,
)


download_button.bind("<Enter>", hover_download_button)
download_button.bind("<Leave>", nohover_download_button)


# Inject-Tab
def get_launcher() -> str:
    global user_launcher
    user_launcher = launcherVar.get()
    if user_launcher == "Steam":
        return 'cmd /c start steam://run/271590' # works perfectly
    elif user_launcher == "Rockstar Games":
        return "rgs"
    elif user_launcher == "Epic Games":
        return 'cmd /c start com.epicgames.launcher://apps/9d2d0eb64d5c44529cece33fe2a46482?action=launch&silent=true'
    else:
        return '_none'
    
def get_rgl_path() -> str:
    regkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\\WOW6432Node\\Rockstar Games\\', 0, winreg.KEY_READ)
    try:
        subkey = winreg.OpenKey(regkey, r"Grand Theft Auto V")
        keyValue = winreg.QueryValueEx(subkey, r"InstallFolder")
        return (keyValue[0])
    except OSError:
        pass

def start_gta():
    find_gta_process()
    if not is_running:
        try:
            run_cmd = get_launcher() # run dmc's cousin
            if run_cmd == "rgs":
                inject_progress_label.configure(text="Please wait while YMU attempts to launch your game through\nRockstar Games Launcher...")
                dummy_progress(injection_progressbar)
                start_gta_button.configure(state = 'disabled')
                rgl_path = get_rgl_path()
                os.startfile(rgl_path + 'PlayGTAV.exe')
                sleep(3)
            elif run_cmd == '_none':
                inject_progress_label.configure(text="Please select your lancher from the dropdown list!", text_color=RED)
                start_gta_button.configure(state = 'disabled')
            else:
                inject_progress_label.configure(text=f"Please wait while YMU attempts to launch your game through\n{user_launcher}...")
                dummy_progress(injection_progressbar)
                start_gta_button.configure(state = 'disabled')
                subprocess.run(run_cmd)
                sleep(3)

            reset_inject_progress_label(5)
            start_gta_button.configure(state = 'normal')

        except Exception as e:
            inject_progress_label.configure(text=f"Error finding a GTA 5 executable\nERROR: {e}", text_color=RED)
            reset_inject_progress_label(10)
            start_gta_button.configure(state = 'normal')
    else:
        inject_progress_label.configure(text="GTA 5 is already running!", text_color=RED)
        reset_inject_progress_label(10)


def start_gta_thread():
    Thread(target=start_gta, daemon=True).start()


injection_progressbar = ctk.CTkProgressBar(
    master=tabview.tab("Inject"),
    orientation="horizontal",
    height=8,
    corner_radius=14,
    fg_color=BG_COLOR_D,
    progress_color=GREEN,
    width=140,
)
injection_progressbar.pack(
    pady=5, padx=5, expand=False, fill="x", side="bottom", anchor="s"
)
injection_progressbar.set(0)


inject_progress_label = ctk.CTkLabel(
    master=tabview.tab("Inject"),
    text="Progress: N/A",
    font=CODE_FONT_SMALL,
    height=10,
    text_color=WHITE,
)
inject_progress_label.pack(
    pady=5, padx=5, expand=False, fill=None, anchor="s", side="bottom"
)


# more info for injection
def open_inject_info(e):
    inject_info = ctk.CTkToplevel(fg_color=BG_COLOR_D)
    inject_info.title("Start GTA5 & Injection Info")
    inject_info.minsize(400, 250)
    inject_info.resizable(False, False)
    width_of_window = 400
    height_of_window = 250
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x_coordinate = (screen_width / 2) - (width_of_window / 2)
    y_coordinate = (screen_height / 2) - (height_of_window / 2)
    inject_info.geometry(
        "%dx%d+%d+%d" % (width_of_window, height_of_window, x_coordinate, y_coordinate)
    )

    def border_frame_hover(e):
        s_i_tabview.configure(border_color=GREEN)

    def border_frame_normal(e):
        s_i_tabview.configure(border_color=GREEN_D)

    s_i_tabview = ctk.CTkTabview(master=inject_info, fg_color=BG_COLOR, corner_radius=12, segmented_button_fg_color=BG_COLOR, segmented_button_selected_color=BG_COLOR_D, segmented_button_selected_hover_color=BG_COLOR, segmented_button_unselected_color=BG_COLOR, segmented_button_unselected_hover_color=BG_COLOR_D, text_color=GREEN, border_color=GREEN_D, border_width=2)
    s_i_tabview.pack(pady=10, padx=10, expand=True, fill="both")
    s_i_tabview.add("⭐ Start GTA5 ⭐")
    s_i_tabview.add("⭐ Inject YimMenu.dll ⭐")

    startgta5_info_label = ctk.CTkLabel(
        master=s_i_tabview.tab("⭐ Start GTA5 ⭐"),
        text='How-To: Select your launcher then press "Start GTA 5".',
        font=CODE_FONT,
        justify="center",
        text_color=GREEN,
    )
    startgta5_info_label.pack(pady=0, padx=0, expand=True, fill="both")    
    inject_info_label = ctk.CTkLabel(
        master=s_i_tabview.tab("⭐ Inject YimMenu.dll ⭐"),
        text="How-To:\n↦ Launch the game.\n↦ Load into 'Single Player'\n↦ Wait for the game to finish loading\n↦ CLick on (Inject YimMenu)\n↦ Wait for YimMenu to finish loading\n↦ Done! ✅",
        font=CODE_FONT,
        justify="center",
        text_color=GREEN,
    )
    inject_info_label.pack(pady=0, padx=0, expand=True, fill="both")
    inject_info.bind("<Enter>", border_frame_hover)
    inject_info.bind("<Leave>", border_frame_normal)
    inject_info.attributes("-topmost", "true")


def hover_inject_mi(e):
    inject_more_info_label.configure(
        text="Click here for more info",
        cursor="hand2",
        text_color=GREEN,
        font=CODE_FONT_U,
    )
    tabview.configure(border_color=GREEN)


def normal_inject_mi(e):
    inject_more_info_label.configure(
        text="↣ Click here for more info ↢",
        cursor="arrow",
        text_color=WHITE,
        font=CODE_FONT,
    )
    tabview.configure(border_color=GREEN_D)


inject_more_info_label = ctk.CTkLabel(
    master=tabview.tab("Inject"),
    text="↣ Click here for more info ↢",
    justify="center",
    font=CODE_FONT,
)
inject_more_info_label.pack(pady=10, padx=10, expand=False, fill=None)


inject_more_info_label.bind("<ButtonRelease>", open_inject_info)
inject_more_info_label.bind("<Enter>", hover_inject_mi)
inject_more_info_label.bind("<Leave>", normal_inject_mi)

launchers_menu = ctk.CTkOptionMenu(
                    master=tabview.tab("Inject"),
                    values=LAUNCHERS,
                    command=set_launcher,
                    fg_color=BG_COLOR_D,
                    text_color=WHITE,
                    bg_color="transparent",
                    button_color=BG_COLOR_D,
                    button_hover_color=GREEN_D,
                    font=SMALL_BOLD_FONT,
                    dynamic_resizing=False,
                    dropdown_fg_color=BG_COLOR_D,
                    dropdown_font=SMALL_FONT,
                    dropdown_hover_color=BG_COLOR,
                    dropdown_text_color=WHITE,
                    corner_radius=8,
                    width=160,
                    ).pack(pady=5, padx=0, expand=False, fill=None)

def hover_buttons_frame(e):
    step_indicator_label.configure(text=s_i_str)


buttons_frame = ctk.CTkFrame(
        master=tabview.tab("Inject"),
        corner_radius=14,
        fg_color=BG_COLOR_D,
        border_width=0, border_color=GREEN_B
    )
buttons_frame.pack(pady=0, padx=0, expand=True, fill=None)
buttons_frame.bind("<Enter>", hover_buttons_frame)

def hover_start_gta_button(e):
    start_gta_button.configure(text_color=GREEN, fg_color=GREEN_B)
    tabview.configure(border_color=GREEN)
    buttons_frame.configure(border_width=1)
    Thread(target=step1_ani, daemon=True).start()


def nohover_start_gta_button(e):
    start_gta_button.configure(text_color=BG_COLOR_D, fg_color=GREEN)
    tabview.configure(border_color=GREEN_D)
    buttons_frame.configure(border_width=0)
    step_indicator_label.configure(text=s_i_str)


start_gta_button = ctk.CTkButton(
    master=buttons_frame,
    text="Start GTA 5",
    command=start_gta_thread,
    fg_color=GREEN,
    hover_color=GREEN_B,
    text_color=BG_COLOR_D,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)


start_gta_button.pack(
    pady=15,
    padx=15,
    expand=False,
    fill=None,
)

start_gta_button.bind("<Enter>", hover_start_gta_button)
start_gta_button.bind("<Leave>", nohover_start_gta_button)

s_i_str = "Step 1: ⤴ | Step 2: ⤵"

s1_i = str("S"+'\u0332'+"tep 1: ⤴ | Step 2: ⤵")
s1_i1 = str("St"+'\u0332'+"ep 1: ⤴ | Step 2: ⤵")
s1_i2 = str("Ste"+'\u0332'+"p 1: ⤴ | Step 2: ⤵")
s1_i3 = str("Step"+'\u0332'+" 1: ⤴ | Step 2: ⤵")
s1_i4 = str("Step"+'\u0332'+" 1: ⤴ | Step 2: ⤵")
s1_i4 = str("Step 1"+'\u0332'+": ⤴ | Step 2: ⤵")
s1_i_ = str("S"+'\u0332'+"tep "+"1"+'\u0332'+": ⤴ | Step 2: ⤵")
s1_i_1 = str("S"+'\u0332'+"t"+'\u0332'+"ep "+"1"+'\u0332'+": ⤴ | Step 2: ⤵")
s1_i_2 = str("S"+'\u0332'+"t"+'\u0332'+"e"+'\u0332'+"p "+"1"+'\u0332'+": ⤴ | Step 2: ⤵")
s1_i_3 = str("S"+'\u0332'+"t"+'\u0332'+"e"+'\u0332'+"p"+'\u0332'+" 1"+'\u0332'+": ⤴ | Step 2: ⤵")


def step1_ani():
    step_indicator_label.configure(text=s1_i)
    sleep(0.01)
    step_indicator_label.configure(text=s1_i1)
    sleep(0.02)
    step_indicator_label.configure(text=s1_i2)
    sleep(0.03)
    step_indicator_label.configure(text=s1_i2)
    sleep(0.04)
    step_indicator_label.configure(text=s1_i3)
    sleep(0.05)
    step_indicator_label.configure(text=s1_i4)
    sleep(0.06)
    step_indicator_label.configure(text=s1_i_)
    sleep(0.05)
    step_indicator_label.configure(text=s1_i_1)
    sleep(0.04)
    step_indicator_label.configure(text=s1_i_2)
    sleep(0.03)
    step_indicator_label.configure(text=s1_i_3)


s2_i = str("Step 1: ⤴ | S"+'\u0332'+"tep 2: ⤵")
s2_i1 = str("Step 1: ⤴ | St"+'\u0332'+"ep 2: ⤵")
s2_i2 = str("Step 1: ⤴ | Ste"+'\u0332'+"p 2: ⤵")
s2_i3 = str("Step 1: ⤴ | Step"+'\u0332'+" 2: ⤵")
s2_i4 = str("Step 1: ⤴ | Step"+'\u0332'+" 2: ⤵")
s2_i4 = str("Step 1: ⤴ | Step 2"+'\u0332'+": ⤵")
s2_i_ = str("Step 1: ⤴ | S"+'\u0332'+"tep "+"2"+'\u0332'+": ⤵")
s2_i_1 = str("Step 1: ⤴ | S"+'\u0332'+"t"+'\u0332'+"ep "+"2"+'\u0332'+": ⤵")
s2_i_2 = str("Step 1: ⤴ | S"+'\u0332'+"t"+'\u0332'+"e"+'\u0332'+"p "+"2"+'\u0332'+": ⤵")
s2_i_3 = str("Step 1: ⤴ | S"+'\u0332'+"t"+'\u0332'+"e"+'\u0332'+"p"+'\u0332'+" 2"+'\u0332'+": ⤵")


def step2_ani():
    step_indicator_label.configure(text=s2_i)
    sleep(0.01)
    step_indicator_label.configure(text=s2_i1)
    sleep(0.02)
    step_indicator_label.configure(text=s2_i2)
    sleep(0.03)
    step_indicator_label.configure(text=s2_i2)
    sleep(0.04)
    step_indicator_label.configure(text=s2_i3)
    sleep(0.05)
    step_indicator_label.configure(text=s2_i4)
    sleep(0.06)
    step_indicator_label.configure(text=s2_i_)
    sleep(0.05)
    step_indicator_label.configure(text=s2_i_1)
    sleep(0.04)
    step_indicator_label.configure(text=s2_i_2)
    sleep(0.03)
    step_indicator_label.configure(text=s2_i_3)


def hover_step_indicator_label(e):
    step_indicator_label.configure(text=s_i_str)


step_indicator_label = ctk.CTkLabel(master=buttons_frame, text=s_i_str, font=CODE_FONT_SMALL, text_color=WHITE)
step_indicator_label.pack(pady=0, padx=0, fill=None, expand=False)
step_indicator_label.bind("<Enter>", hover_step_indicator_label)


def hover_inject_button(e):
    inject_button.configure(text_color=GREEN, fg_color=GREEN_B)
    tabview.configure(border_color=GREEN)
    buttons_frame.configure(border_width=1)
    Thread(target=step2_ani, daemon=True).start()


def nohover_inject_button(e):
    inject_button.configure(text_color=BG_COLOR_D, fg_color=GREEN)
    tabview.configure(border_color=GREEN_D)
    buttons_frame.configure(border_width=0)
    step_indicator_label.configure(text=s_i_str)


inject_button = ctk.CTkButton(
    master=buttons_frame,
    text="Inject YimMenu",
    command=start_injection,
    fg_color=GREEN,
    hover_color=GREEN_B,
    text_color=BG_COLOR_D,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)


inject_button.pack(
    pady=15,
    padx=15,
    expand=False,
    fill=None,
)

inject_button.bind("<Enter>", hover_inject_button)
inject_button.bind("<Leave>", nohover_inject_button)


# settings tab

settings_frame = ctk.CTkScrollableFrame(
        master=tabview.tab("Settings Ξ"),
        corner_radius=8,
        scrollbar_button_color=GREEN_B,
        scrollbar_button_hover_color=GREEN_D,
        scrollbar_fg_color=BG_COLOR,
        fg_color=BG_COLOR,
    )
settings_frame.pack(pady=0, padx=0, expand=True, fill="both")


def change_theme(e):
    config = ConfigParser()
    config.read(CONFIGPATH)
    theme = appearance_mode_optionemenu.get()
    if theme == "Dark":
        appearance_mode_optionemenu.set("Dark")
        ctk.set_appearance_mode("dark")
        config.set("ymu", "theme", "dark")
    elif theme == "Light":
        appearance_mode_optionemenu.set("Light")
        ctk.set_appearance_mode("light")
        config.set("ymu", "theme", "light")
    else:
        appearance_mode_optionemenu.set("Dark")
        ctk.set_appearance_mode("dark")
        config.set("ymu", "theme", "dark")
    with open(CONFIGPATH, "w") as configfile:
        config.write(configfile)


appearance_mode_label = ctk.CTkLabel(
    master=settings_frame,
    text="▸ Set YMU Theme ◂",
    font=BIG_FONT,
    text_color=WHITE,
)

appearance_mode_label.pack(pady=0, padx=0, expand=False, fill=None)

appearance_mode_optionemenu = ctk.CTkOptionMenu(
    master=settings_frame,
    values=["Light", "Dark"],
    command=change_theme,
    fg_color=BG_COLOR_D,
    text_color=WHITE,
    bg_color="transparent",
    button_color=BG_COLOR_D,
    button_hover_color=GREEN_D,
    font=SMALL_BOLD_FONT,
    dynamic_resizing=False,
    dropdown_fg_color=BG_COLOR_D,
    dropdown_font=SMALL_FONT,
    dropdown_hover_color=BG_COLOR,
    dropdown_text_color=WHITE,
    corner_radius=8,
    width=80,
)

appearance_mode_optionemenu.pack(pady=5, padx=0, expand=False, fill=None)


def set_optionmenu():
    config = ConfigParser()
    config.read(CONFIGPATH)
    if config["ymu"]["theme"] == "dark":
        appearance_mode_optionemenu.set("Dark")
    elif config["ymu"]["theme"] == "light":
        appearance_mode_optionemenu.set("Light")
    else:
        appearance_mode_optionemenu.set("Dark")


set_optionmenu()


def check_lua_setting_on_startup():
    yimPath = f'{os.getenv('APPDATA')}\\yimmenu'
    yimSettings = f'{yimPath}\\settings.json'
    if os.path.exists(yimPath) and os.path.isfile(yimSettings):
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["lua"]
            key = "enable_auto_reload_changed_scripts"
            if key in setting:
                if setting[key] is True:
                    lua_ar_switch.select()
                    lua_ar_switch.configure(text=f"Enable Auto Reload for Lua-Scripts? ({lua_ar_switch.get()})", button_color=GREEN, button_hover_color=GREEN_D, border_color=GREEN_D)
                elif setting[key] is False:
                    lua_ar_switch.deselect()
                    lua_ar_switch.configure(text=f"Enable Auto Reload for Lua-Scripts? ({lua_ar_switch.get()})", button_color=RED, button_hover_color=RED_D, border_color=RED_D)


# Enable auto-reload for Lua scripts
def lua_auto_reload():
    yimPath = f'{os.getenv('APPDATA')}\\yimmenu'
    yimSettings = f'{yimPath}\\settings.json'
    if os.path.exists(yimPath) and os.path.isfile(yimSettings) and lua_ar_switch.get()=="ON":
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["lua"]
            key = "enable_auto_reload_changed_scripts"
            if key in setting:
                if setting[key] is False:
                    setting[key] = True
                    with open(yimSettings, 'w') as newFile:
                        json.dump(data, newFile)
        lua_ar_switch.configure(text=f"Enable Auto Reload for Lua-Scripts? ({lua_ar_switch.get()})")
        lua_ar_switch.configure(button_color=GREEN, button_hover_color=GREEN_D, border_color=GREEN_D)

    elif os.path.exists(yimPath) and os.path.isfile(yimSettings) and lua_ar_switch.get()=="OFF":
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["lua"]
            key = "enable_auto_reload_changed_scripts"
            if key in setting:
                if setting[key] is True:
                    setting[key] = False
                    with open(yimSettings, 'w') as newFile:
                        json.dump(data, newFile)
        lua_ar_switch.configure(text=f"Enable Auto Reload for Lua-Scripts? ({lua_ar_switch.get()})")
        lua_ar_switch.configure(button_color=RED, button_hover_color=RED_D, border_color=RED_D)

    else:
        lua_ar_switch.configure(text="❌ YimMenu isn't installed!\nOr has never been injected.", text_color=RED)
        sleep(5)
        lua_ar_switch.configure(text="Enable Auto Reload for Lua-Scripts?", text_color=RED)


luas_header = ctk.CTkLabel(master=settings_frame, text="▸ Lua Settings ◂", text_color=WHITE, font=BIG_FONT, bg_color="transparent", fg_color="transparent")
luas_header.pack(pady=10, padx=0)


lua_settings_frame = ctk.CTkFrame(
        master=settings_frame,
        corner_radius=21,
        fg_color=BG_COLOR_D,
        border_width=0, border_color=GREEN_B
    )
lua_settings_frame.pack(pady=0, padx=0, expand=True, fill=None)


def lua_ar_switch_hover(e):
    tabview.configure(border_color=GREEN)
    lua_settings_frame.configure(border_width=1)
    if lua_ar_switch.get() == "ON":
        lua_ar_switch.configure(button_color=GREEN_D, border_color=GREEN_D, font=SMALL_BOLD_FONT_U)
    elif lua_ar_switch.get() == "OFF":
        lua_ar_switch.configure(button_color=RED_D, border_color=RED_D, font=SMALL_BOLD_FONT_U)


def lua_ar_switch_normal(e):
    tabview.configure(border_color=GREEN_D)
    lua_settings_frame.configure(border_width=0)
    if lua_ar_switch.get() == "ON":
        lua_ar_switch.configure(button_color=GREEN, border_color=GREEN, font=SMALL_BOLD_FONT)
    elif lua_ar_switch.get() == "OFF":
        lua_ar_switch.configure(button_color=RED, border_color=RED, font=SMALL_BOLD_FONT)


lua_ar_switch = ctk.CTkSwitch(
    master=lua_settings_frame,
    onvalue="ON",
    offvalue="OFF",
    text="Enable Auto Reload for Lua-Scripts? (OFF)",
    fg_color=BG_COLOR,
    button_color=RED_D,
    button_hover_color=RED,
    border_width=1,
    border_color=RED_D,
    corner_radius=10,
    font=SMALL_BOLD_FONT,
    progress_color=BG_COLOR,
    text_color=WHITE,
    bg_color="transparent", command=lua_auto_reload
)
lua_ar_switch.pack(pady=15, padx=15, fill=None, expand=False)

lua_ar_switch.bind("<Enter>", lua_ar_switch_hover)
lua_ar_switch.bind("<Leave>", lua_ar_switch_normal)

luas_label = ctk.CTkLabel(master=lua_settings_frame, text="↘ Don't have any Luas? ↙", text_color=WHITE, font=SMALL_BOLD_FONT, bg_color="transparent", fg_color="transparent",)
luas_label.pack(pady=0, padx=0, fill=None, expand=False)


def open_luas():
    webbrowser.open_new_tab("https://github.com/orgs/YimMenu-Lua/repositories")


def discover_luas_hover(e):
    discover_luas_button.configure(text_color=GREEN, fg_color=GREEN_B)
    luas_label.configure(font=SMALL_BOLD_FONT_U, text="Don't have any Luas?")
    lua_settings_frame.configure(border_width=1)
    tabview.configure(border_color=GREEN)


def discover_luas_normal(e):
    discover_luas_button.configure(text_color=BG_COLOR_D, fg_color=GREEN)
    luas_label.configure(font=SMALL_BOLD_FONT, text="↘ Don't have any Luas? ↙")
    lua_settings_frame.configure(border_width=0)
    tabview.configure(border_color=GREEN_D)


discover_luas_button = ctk.CTkButton(master=lua_settings_frame, fg_color=GREEN, text="Discover Luas ↗", font=SMALL_BOLD_FONT, text_color=BG_COLOR_D, bg_color="transparent", corner_radius=8, hover_color=GREEN_B, command=open_luas)

discover_luas_button.pack(pady=15, padx=0, expand=False, fill = None)

discover_luas_button.bind("<Enter>", discover_luas_hover)
discover_luas_button.bind("<Leave>", discover_luas_normal)

others_header = ctk.CTkLabel(master=settings_frame, text="▸ Other Settings ◂", text_color=WHITE, font=BIG_FONT, bg_color="transparent", fg_color="transparent")
others_header.pack(pady=10, padx=0)

other_settings_frame = ctk.CTkFrame(
        master=settings_frame,
        corner_radius=21,
        fg_color=BG_COLOR_D,
        border_color=GREEN_B,
        border_width=0
    )
other_settings_frame.pack(pady=0, padx=0, expand=False, fill=None)


def check_console_setting_on_startup():
    yimPath = f'{os.getenv('APPDATA')}\\yimmenu'
    yimSettings = f'{yimPath}\\settings.json'
    if os.path.exists(yimPath) and os.path.isfile(yimSettings):
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["debug"]
            key = "external_console"
            if key in setting:
                if setting[key] is True:
                    e_console_switch.select()
                    e_console_switch.configure(text=f"Enable External Debug Console? ({e_console_switch.get()})", button_color=GREEN, button_hover_color=GREEN_D, border_color=GREEN_D)
                elif setting[key] is False:
                    e_console_switch.deselect()
                    e_console_switch.configure(text=f"Enable External Debug Console? ({e_console_switch.get()})", button_color=RED, button_hover_color=RED_D, border_color=RED_D)


def external_console():
    yimPath = f'{os.getenv('APPDATA')}\\yimmenu'
    yimSettings = f'{yimPath}\\settings.json'
    if os.path.exists(yimPath) and os.path.isfile(yimSettings) and e_console_switch.get() == "ON":
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["debug"]
            key = "external_console"
            if key in setting:
                if setting[key] is False:
                    setting[key] = True
                    with open(yimSettings, 'w') as newFile:
                        json.dump(data, newFile)
        e_console_switch.configure(text=f"Enable External Debug Console? ({e_console_switch.get()})")
        e_console_switch.configure(button_color=GREEN, button_hover_color=GREEN_D,border_color=GREEN_D)

    elif os.path.exists(yimPath) and os.path.isfile(yimSettings) and e_console_switch.get() == "OFF":
        with open(yimSettings, "r") as jsonfile:
            data = json.load(jsonfile)
            setting = data["debug"]
            key = "external_console"
            if key in setting:
                if setting[key] is True:
                    setting[key] = False
                    with open(yimSettings, 'w') as newFile:
                        json.dump(data, newFile)
        e_console_switch.configure(text=f"Enable External Debug Console? ({e_console_switch.get()})")
        e_console_switch.configure(button_color=RED, button_hover_color=RED_D, border_color=RED_D)

    else:
        e_console_switch.configure(text="❌ YimMenu isn't installed!\nOr has never been injected.", text_color=RED)
        sleep(5)
        e_console_switch.configure(text=f"Enable External Debug Console? ({e_console_switch.get()})", text_color=RED)


def e_console_switch_hover(e):
    tabview.configure(border_color=GREEN)
    other_settings_frame.configure(border_width=1)
    if e_console_switch.get() == "ON":
        e_console_switch.configure(button_color=GREEN_D, border_color=GREEN_D, font=SMALL_BOLD_FONT_U)
    elif e_console_switch.get() == "OFF":
        e_console_switch.configure(button_color=RED_D, border_color=RED_D, font=SMALL_BOLD_FONT_U)


def e_console_switch_normal(e):
    tabview.configure(border_color=GREEN_D)
    other_settings_frame.configure(border_width=0)
    if e_console_switch.get() == "ON":
        e_console_switch.configure(button_color=GREEN, border_color=GREEN, font=SMALL_BOLD_FONT)
    elif e_console_switch.get() == "OFF":
        e_console_switch.configure(button_color=RED, border_color=RED, font=SMALL_BOLD_FONT)


e_console_switch = ctk.CTkSwitch(
    master=other_settings_frame,
    onvalue="ON",
    offvalue="OFF",
    text="Enable External Debug Console? (OFF)",
    fg_color=BG_COLOR,
    button_color=RED_D,
    button_hover_color=RED,
    border_width=1,
    border_color=RED_D,
    corner_radius=10,
    font=SMALL_BOLD_FONT,
    progress_color=BG_COLOR,
    text_color=WHITE,
    bg_color="transparent", command=external_console
)
e_console_switch.pack(pady=15, padx=15, fill=None, expand=False)

e_console_switch.bind("<Enter>", e_console_switch_hover)
e_console_switch.bind("<Leave>", e_console_switch_normal)


def open_yimdir():
    yimPath = f'{os.getenv('APPDATA')}\\yimmenu'
    if not os.path.exists(yimPath):
        pass
    else:
        os.system(f"explorer.exe {yimPath}")


def folder_button_hover(e):
    folder_button.configure(
        image=folder_hvr, text_color=GREEN, font=SMALL_BOLD_FONT_U)
    tabview.configure(border_color=GREEN)
    other_settings_frame.configure(border_width=1)


def folder_button_normal(e):
    folder_button.configure(image=folder_white, text_color=WHITE, font=SMALL_BOLD_FONT)
    tabview.configure(border_color=GREEN_D)
    other_settings_frame.configure(border_width=0)


folder_button = ctk.CTkButton(
    master=other_settings_frame,
    text='Open "YimMenu"-Folder',
    image=folder_white,
    command=open_yimdir,
    fg_color=BG_COLOR_D,
    hover_color=BG_COLOR_D,
    text_color=WHITE,
    font=SMALL_BOLD_FONT,
    corner_radius=10,
)
folder_button.pack(
    pady=0,
    padx=0,
    expand=False,
    fill=None,
)
folder_button.bind("<Enter>", folder_button_hover)
folder_button.bind("<Leave>", folder_button_normal)


def hover_ymu_update_button(e):
    ymu_update_button.configure(text_color=GREEN, fg_color=GREEN_B)
    tabview.configure(border_color=GREEN)
    other_settings_frame.configure(border_width=1)


def nohover_ymu_update_button(e):
    ymu_update_button.configure(text_color=BG_COLOR_D, fg_color=GREEN)
    tabview.configure(border_color=GREEN_D)
    other_settings_frame.configure(border_width=0)


ymu_update_button = ctk.CTkButton(
    master=other_settings_frame,
    text="Check For YMU Updates",
    command=ymu_update_thread,
    fg_color=GREEN,
    hover_color=GREEN_D,
    text_color=BG_COLOR_D,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)
ymu_update_button.pack(
    pady=15,
    padx=0,
    expand=False,
    fill=None,
)

ymu_update_button.bind("<Enter>", hover_ymu_update_button)
ymu_update_button.bind("<Leave>", nohover_ymu_update_button)

update_response = ctk.CTkLabel(
    master=other_settings_frame,
    textvariable=ymu_update_message,
    text_color=WHITE, font=CODE_FONT_SMALL
)

if __name__ == "__main__":

    # v1.0.6 only - moving old dll-Folder and dll-File to ymu directory
    if os.path.exists("dll"):
        os.rename("dll", "ymu/dll")
        if os.path.isfile("dll/YimMenu.dll"):
            os.rename("dll/YimMenu.dll", "ymu/dll/YimMenu.dll")
        else:
            pass
    else:
        pass
    # will be removed in v1.0.7 ↑

    Thread(target=check_lua_setting_on_startup, daemon=True).start()
    Thread(target=check_console_setting_on_startup, daemon=True).start()
    Thread(target=refresh_download_button, daemon=True).start()
    if getattr(sys, 'frozen', False):
        pyi_splash.close()
    root.mainloop()
    try:
        if start_self_update:
            os.execvp("./ymu_self_updater.exe", ["ymu_self_updater"])
    except NameError:
        pass
