# Libraries YMU depends on
import customtkinter as ctk
import hashlib
import os
import psutil
import requests
import sys
import webbrowser
from bs4 import BeautifulSoup
from ctypes import *
from customtkinter import CTkFont
from pyinjector import inject
from threading import Thread
from time import sleep


# show a splash screen when the executable is loading. Ignore the 'not resolved' error, the module is part of PyInstaller not Python.
if getattr(sys, 'frozen', False):
    import pyi_splash


# properly pack the icon so we don't have to include it with the exe each time.
def resource_path(relative_path):
        # Since we're using --onefile command, PyInstaller will create a temp folder and store the path in _MEIPASS
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

# YMU Appearance - currently only dark mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# Colors
BG_COLOR = "#333333"
DBG_COLOR = "#2b2b2b"
FG_COLOR = "#45e876"
BHVR_COLOR = "#36543F"
WHITE = "#DCE4EE"


# YMU root - title - minsize - launch size - launch in center of sreen
root = ctk.CTk()
root.title("YMU - YimMenuUpdater")
root.resizable(False, False)
root.iconbitmap(resource_path('icon\\ymu.ico'))
root.minsize(260, 350)
root.configure(fg_color=DBG_COLOR)
width_of_window = 400
height_of_window = 400
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
BOLD_FONT = CTkFont(family="Manrope", size=14, weight="bold")
TOOLTIP_FONT = CTkFont(family="Manrope", size=12, slant="italic")
CODE_FONT = CTkFont(family="JetBrains Mono", size=12)
CODE_FONT_BIG = CTkFont(family="JetBrains Mono", size=16)
CODE_FONT_SMALL = CTkFont(family="JetBrains Mono", size=10)

# Version, Url and Paths
LOCAL_VER = "1.0.2"
SELFDIR = './ymu.exe'
DLLURL = "https://github.com/YimMenu/YimMenu/releases/download/nightly/YimMenu.dll"
DLLDIR = "./dll"
LOCALDLL = "./dll/YimMenu.dll"


#get YMU's version for future self update function:
ymu_update_message = ctk.StringVar()

def get_ymu_ver():

    try:

        r = requests.get('https://github.com/NiiV3AU/YMU/tags')
        soup = BeautifulSoup(r.content, 'html.parser')
        result = soup.find(class_= 'Link--primary Link')
        s = str(result)
        result = s.replace('</a>', '')
        charLength = len(result)
        latest_version = result[charLength - 5:]
        return latest_version
    
    except Exception:
        ymu_update_message.set("❌ Failed to get the latest Github version.\nCheck your Internet connection and try again.")
        update_response.configure(text_color = 'yellow')
        sleep(5)
        ymu_update_message.set("")
        ymu_update_button.configure(state='normal')


def check_for_ymu_update():
    ymu_update_button.configure(state='disabled')
    YMU_VERSION = get_ymu_ver()

    try:

        if LOCAL_VER < YMU_VERSION:
            ymu_update_message.set(f'Update v{YMU_VERSION} is available.')
            update_response.configure(text_color = 'green')
            ymu_update_button.configure(state='normal', text = "Open Github")
            sleep(0.2)
            change_update_button()

        elif LOCAL_VER == YMU_VERSION:
            ymu_update_message.set("YMU is up-to-date ✅")
            update_response.configure(text_color = WHITE)
            sleep(3)
            ymu_update_message.set("")
            ymu_update_button.configure(state='normal')

        elif LOCAL_VER > YMU_VERSION:
            ymu_update_message.set("⚠️ Invalid version detected ⚠️\nPlease download YMU from the official Github repository.")
            update_response.configure(text_color = 'red')
            ymu_update_button.configure(state='normal', text = "Open Github")
            sleep(0.2)
            change_update_button()

    except Exception:
        pass


def open_github_release():
    # for now, just open the browser and let the user manually download and apply the update.
    # we will implement an automated update system later.
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU/releases")


def change_update_button():
    ymu_update_button.configure(command = open_github_release)
    

def ymu_update_thread():
    ymu_update_message.set("Please wait...")
    Thread(target=check_for_ymu_update, daemon=True).start()


# scrapes the release/build SHA256 of the latest YimMenu release
def get_remote_sha256():
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
    global pid # <- I know it's a bad habit but if it works why fix it? 😂
    global is_running
    global injBtnState
    for p in psutil.process_iter(["name", "exe", "cmdline"]):    
        if "GTA5.exe" == p.info['name'] or \
            p.info['exe'] and os.path.basename(p.info['exe']) == "GTA5.exe" or \
            p.info['cmdline'] and p.info['cmdline'][0] == "GTA5.exe":
            pid = p.pid
            is_running = True
            sleep(0.5)
            break
        else:
            pid = 0
            is_running = False

def process_search_thread():
    Thread(target = find_gta_process, daemon = True).start()

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
        progress_prcnt_label.configure(text="YimMenu is up to date.", text_color=BG_COLOR)
        progressbar.set(1.0)

    else:
        download_button.configure(state="normal")
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} available!", text_color="green"
        )
        progressbar.set(0)


# downloads the dll from github and displays progress in a progressbar
def download_dll():
    reset_progress_prcnt_label()
    if not os.path.exists(DLLDIR):
        os.makedirs(DLLDIR)
    try:
        with requests.get(DLLURL, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            progressbar.set(0)
            downloaded_size = 0
            with open(LOCALDLL, "wb") as f:
                for chunk in r.iter_content(chunk_size=128000):  # 64 KB chunks
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = downloaded_size / total_size
                    progressbar.set(progress)
                    progress_prcnt_label.configure(
                        text=f"Progress: {int(progress*100)}%"
                    )
                    progress_prcnt_label.update_idletasks()  # Aktualisiere das Label
        # if download successful
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} successful", text_color=FG_COLOR
        )
        sleep(5)
        check_if_dll_is_downloaded()
        if not os.path.exists(LOCALDLL):
            progress_prcnt_label.configure(
            text="File was removed!\nMake sure to either turn off your antivirus or add YMU folder to exceptions.", text_color = 'red'
            )
            sleep(5)
        Thread(target=refresh_download_button, daemon=True).start()


    # if download failed
    except requests.exceptions.RequestException as e:
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} error: {e}", text_color="red"
        )
        reset_progress_prcnt_label()


# starts the download in a thread to keep the gui responsive
def start_download():
    download_button.configure(state = 'disabled')
    Thread(target=download_dll, daemon=True).start()


# Injects YimMenu into GTA5.exe process
def inject_yimmenu():
    try:
        inject_button.configure(state = 'disabled')
        inject_progress_label.configure(
            text=f"🔍 Searching for GTA5 process...",
            text_color='white',
        )
        dummy_progress(injection_progressbar)
        process_search_thread()
        sleep(1) # give it time to update the values
        injection_progressbar.set(0)
        if pid != 0:
            if os.path.isfile(LOCALDLL):
                inject_progress_label.configure(
                    text=f"Found process 'GTA5.exe' with PID: [{pid}]", 
                    text_color=FG_COLOR
                )
                sleep(2)
                inject_progress_label.configure(
                    text=f"💉Injecting...", 
                    text_color=FG_COLOR
                )
                dummy_progress(injection_progressbar)
                inject(pid, LOCALDLL)
                sleep(2)
                inject_progress_label.configure(
                    text=f"Successfully injected YimMenu.dll into GTA5.exe",
                    text_color=FG_COLOR,
                )
                sleep(3)
                injection_progressbar.set(0)
                process_search_thread()
                sleep(5) # Wait for 5 seconds and check if the game crashes on injection.
                if is_running:
                    inject_progress_label.configure(
                        text="Have fun!",
                        text_color=FG_COLOR,
                    )
                    sleep(5) # exit the app after successful injection. If the game crashes, the program continues to run
                    root.destroy() # if you don't want this behavior feel free to remove it. I just thought it would be nice to free some resources for people with potato PCs.
                else:
                        inject_progress_label.configure(
                        text="Uh Oh! Did your game crash?",
                        text_color="red",
                    )
                sleep(10)
                reset_inject_progress_label()

            else:
                inject_progress_label.configure(
                    text="YimMenu.dll not found! Download the latest release\nand make sure your anti-virus is not interfering.", 
                    text_color="red"
                )
                sleep(5)
                reset_inject_progress_label()

        else:
            inject_progress_label.configure(
                text=f"GTA5.exe not found! Please start the game.", 
                text_color="red")
            sleep(5)
            reset_inject_progress_label()

        inject_button.configure(state = 'normal')

    except Exception:
        injection_progressbar.set(0)
        inject_progress_label.configure(
            text="Failed to inject YimMenu!",
            text_color="red",
        )
        sleep(5)
        reset_inject_progress_label()
        inject_button.configure(state = 'normal')

def start_injection():
    Thread(target=inject_yimmenu, daemon=True).start()

def dummy_progress(widget):
    for i in range (0, 11):
        i += 0.01
        widget.set(i/10)
        sleep(0.05)


def reset_inject_progress_label():
    sleep(3)
    inject_progress_label.configure(text=f"Ready", text_color=WHITE)
    injection_progressbar.set(0)


# opens github repo
def open_github(e):
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU")


# label for github repo - author (NV3) - version
copyright_label = ctk.CTkLabel(
    master=root,
    font=CODE_FONT_SMALL,
    text_color=BG_COLOR,
    text=f"↣ Click Here for GitHub Repo ↢\n⋉ © NV3 ⋊\nf{LOCAL_VER}",
    bg_color="transparent",
    fg_color=DBG_COLOR,
    justify="center",
)
copyright_label.pack(pady=10, fill=None, expand=False, anchor="n", side="top")

copyright_label.bind("<ButtonRelease>", open_github)


# basic ahh animation for copyright_label
def copyright_label_ani_master():

    while True:
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


# starts all animations - currently only copyright
def master_ani_start():
    Thread(target=copyright_label_ani_master, daemon=True).start()


root.after(1000, master_ani_start)


# Download and SHA256 tabs
tabview = ctk.CTkTabview(
    master=root,
    fg_color=BG_COLOR,
    bg_color="transparent",
    corner_radius=12,
    segmented_button_fg_color=DBG_COLOR,
    segmented_button_selected_color=BHVR_COLOR,
    segmented_button_selected_hover_color=BHVR_COLOR,
    segmented_button_unselected_color=BG_COLOR,
    segmented_button_unselected_hover_color=BHVR_COLOR,
    text_color=FG_COLOR,
)
tabview.pack(pady=10, padx=10, expand=True, fill="both")

def refresh_download_tab():
    if check_if_dll_is_downloaded() == "Download":
        tabview.add("Download")
    else:
        tabview.add("Update")

refresh_download_tab()


tabview.add("Inject")
tabview.add("⚙️ Settings")


# reset progress label
def reset_progress_prcnt_label():
    sleep(3)
    progress_prcnt_label.configure(text="", text_color=WHITE)
    progressbar.set(0)


progressbar = ctk.CTkProgressBar(
    master=tabview.tab(check_if_dll_is_downloaded()),
    orientation="horizontal",
    height=8,
    corner_radius=14,
    fg_color=DBG_COLOR,
    progress_color=FG_COLOR,
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
    download_button.configure(text_color=FG_COLOR)
    download_button.configure(fg_color="#36543F")


def nohover_download_button(e):
    download_button.configure(text_color=BG_COLOR)
    download_button.configure(fg_color=FG_COLOR)


def hover_inject_button(e):
    inject_button.configure(text_color=FG_COLOR)
    inject_button.configure(fg_color="#36543F")


def nohover_inject_button(e):
    inject_button.configure(text_color=BG_COLOR)
    inject_button.configure(fg_color=FG_COLOR)


# more info for Download
def open_download_info(e):

    download_info = ctk.CTkToplevel(root, fg_color=BG_COLOR)
    download_info.title("YMU - Download Info")
    download_info.minsize(280, 120)
    download_info.resizable(False, False)

    download_info_label = ctk.CTkLabel(
        master=download_info,
        text=f'⭐ {check_if_dll_is_downloaded()} YimMenu.dll ⭐\n\nHow-To:\n↦ CLick on ({check_if_dll_is_downloaded()})\n↦ CLick on ({check_if_dll_is_downloaded()})\n↪ Wait for the download to finish\n↪ file in "YMU/dll"-folder\n\nIf the file gets deleted,\nadd an exception in\nyour antivirus or\ndisable it.',
        font=CODE_FONT,
        justify="center",
        text_color=FG_COLOR,
    )
    download_info_label.pack(pady=10, padx=10, expand=True, fill="both")


def hover_download_mi(e):
    download_more_info_label.configure(cursor="hand2")
    download_more_info_label.configure(text_color=FG_COLOR)


def normal_download_mi(e):
    download_more_info_label.configure(cursor="arrow")
    download_more_info_label.configure(text_color=WHITE)


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
    changelog = ctk.CTkToplevel(fg_color=BG_COLOR)
    changelog.title("YimMenu Changelog")
    changelog_x_coord = screen_width / 4
    changelog_y_coord = screen_height * 0.2
    changelog.geometry(
        '640x640+' + str(changelog_x_coord) + '+' + str(changelog_y_coord)
    )
    changelog_frame = ctk.CTkScrollableFrame(
        master=changelog,
        corner_radius=10,
        scrollbar_button_color=BHVR_COLOR,
        scrollbar_button_hover_color=FG_COLOR,
        scrollbar_fg_color=DBG_COLOR,
        label_font=BOLD_FONT,
        label_text="YimMenu - Changelog:",
        label_text_color=FG_COLOR,
        label_fg_color=DBG_COLOR,
        fg_color=BG_COLOR,
    )
    changelog_frame.pack(pady=10, padx=10, expand=True, fill="both")
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


def hover_changelog_l(e):
    changelog_l.configure(cursor="hand2")
    changelog_l.configure(text_color=FG_COLOR)


def normal_changelog_l(e):
    changelog_l.configure(cursor="arrow")
    changelog_l.configure(text_color=WHITE)


changelog_l = ctk.CTkLabel(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text="↣ Click here for Changelog ↢",
    justify="center",
    font=CODE_FONT,
)
changelog_l.pack(pady=10, padx=10, expand=False, fill=None)


changelog_l.bind("<ButtonRelease>", open_changelog)
changelog_l.bind("<Enter>", hover_changelog_l)
changelog_l.bind("<Leave>", normal_changelog_l)


download_button = ctk.CTkButton(
    master=tabview.tab(check_if_dll_is_downloaded()),
    text=f"{check_if_dll_is_downloaded()}",
    command=start_download,
    fg_color=FG_COLOR,
    hover_color=BHVR_COLOR,
    text_color=BG_COLOR,
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

refresh_download_button()


# Inject-Tab
injection_progressbar = ctk.CTkProgressBar(
    master=tabview.tab("Inject"),
    orientation="horizontal",
    height=8,
    corner_radius=14,
    fg_color=DBG_COLOR,
    progress_color=FG_COLOR,
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

    inject_info = ctk.CTkToplevel(root, fg_color=BG_COLOR)
    inject_info.title("YMU - Injection Info")
    inject_info.minsize(280, 120)
    inject_info.resizable(False, False)

    inject_info_label = ctk.CTkLabel(
        master=inject_info,
        text="⭐ Inject YimMenu.dll ⭐\n\nHow-To:\n↦ Launch the game.\n↦ Load into 'Single Player'.\n↦ Wait for the game to finish loading.\n↦ CLick on (Inject YimMenu).\n↦ Wait for YimMenu to finish loading.\n↦ Done! ✅",
        font=CODE_FONT,
        justify="center",
        text_color=FG_COLOR,
    )
    inject_info_label.pack(pady=10, padx=10, expand=True, fill="both")


def hover_inject_mi(e):
    inject_more_info_label.configure(cursor="hand2")
    inject_more_info_label.configure(text_color=FG_COLOR)


def normal_inject_mi(e):
    inject_more_info_label.configure(cursor="arrow")
    inject_more_info_label.configure(text_color=WHITE)


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


inject_button = ctk.CTkButton(
    master=tabview.tab("Inject"),
    text="Inject YimMenu",
    command=start_injection,
    fg_color=FG_COLOR,
    hover_color=BHVR_COLOR,
    text_color=BG_COLOR,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)


inject_button.pack(
    pady=10,
    padx=5,
    expand=True,
    fill=None,
)

inject_button.bind("<Enter>", hover_inject_button)
inject_button.bind("<Leave>", nohover_inject_button)


# settings tab

version_label = ctk.CTkLabel(
    master=tabview.tab("⚙️ Settings"),
    text=f'v{LOCAL_VER}',
    text_color="#D3D3D3",
    justify="right",
    anchor= "nw",
    font=SMALL_FONT,
)
version_label.pack(pady=10, padx=10, expand=False, fill=None)


def hover_ymu_update_button(e):
    ymu_update_button.configure(text_color=FG_COLOR)
    ymu_update_button.configure(fg_color="#36543F")


def nohover_ymu_update_button(e):
    ymu_update_button.configure(text_color=BG_COLOR)
    ymu_update_button.configure(fg_color=FG_COLOR)

def change_theme(theme: str):
    ctk.set_appearance_mode(theme)

ymu_update_button = ctk.CTkButton(
    master=tabview.tab("⚙️ Settings"),
    text="Check For Update",
    command=ymu_update_thread,
    fg_color=FG_COLOR,
    hover_color=BHVR_COLOR,
    text_color=BG_COLOR,
    font=SMALL_BOLD_FONT,
    corner_radius=8,
)
ymu_update_button.pack(
    pady=10,
    padx=5,
    expand=True,
    fill=None,
)

ymu_update_button.bind("<Enter>", hover_ymu_update_button)
ymu_update_button.bind("<Leave>", nohover_ymu_update_button)

update_response = ctk.CTkLabel(
    master=tabview.tab("⚙️ Settings"),
    textvariable = ymu_update_message,
    text_color = WHITE,
)
update_response.pack(
    pady=5, padx=5, expand=False, fill=None, anchor="s"
)

# appearance_mode_label = ctk.CTkLabel(master = tabview.tab("⚙️ Settings"), 
#                                      text = "Theme:")
# appearance_mode_label.pack(
#     pady=5, padx=5, expand=False, fill=None, anchor="s"
# )

# appearance_mode_optionemenu = ctk.CTkOptionMenu(master = tabview.tab("⚙️ Settings"), 
#                                                 values = ["Light", "Dark", "System"],
#                                                 command = change_theme
#                                                 )
# appearance_mode_optionemenu.pack(
#     pady=5, padx=5, expand=False, fill=None, anchor="s", side="bottom"
# )
# appearance_mode_optionemenu.set("Dark")


if getattr(sys, 'frozen', False):
    pyi_splash.close()

if __name__ == "__main__":
    root.mainloop()