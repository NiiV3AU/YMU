# Libraries YMU depends on
import os
import psutil
import customtkinter as ctk
import requests
import hashlib
import webbrowser
from customtkinter import CTkFont
from threading import Thread
from time import sleep as sleep
from ctypes import *
from pyinjector import inject
from bs4 import BeautifulSoup

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
root.iconbitmap("ymu.ico")
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

# Url and Paths
DLLURL = "https://github.com/YimMenu/YimMenu/releases/download/nightly/YimMenu.dll"
DLLDIR = "./dll"
LOCALDLL = "./dll/YimMenu.dll"

# Injector
PROCNAME = "GTA5.exe"
PID = 0000
PAGE_READWRITE = 0x04
PROCESS_ALL_ACCESS = 0x00F0000 | 0x00100000 | 0xFFF
VIRTUAL_MEM = 0x1000 | 0x2000
INJECT_MSG = ""


# self explanatory
def check_if_dll_is_downloaded():
    while True:
        if os.path.exists(DLLDIR):
            return "Update"
        else:
            return "Download"


# scrapes the release/build SHA256 of the latest YimMenu release
def get_remote_sha256():
    r = requests.get("https://github.com/YimMenu/YimMenu/releases/latest")
    soup = BeautifulSoup(r.content, "html.parser")
    list = soup.find(class_="notranslate")
    l = list("code")
    s = str(l)
    tag = s.replace("[<code>", "")  # remove the first <code> tag from the string.
    sep = " "  # the build SHA in YimMenu's Github release page has a space between the actual hash and the word 'YimMenu.dll'. We can use this space to split the string.
    head, sep, _ = tag.partition(
        sep
    )  # split the return string into 3 parts: 'head' is the hash we're after, 'sep' is the space separator and the rest is ignored.
    REM_SHA = head
    REM_SHA_LENG = len(
        REM_SHA
    )  # not sure if this is useful for YMU but I was using it while testing to make sure the hash is exactly 64 characters long.
    if REM_SHA_LENG == 64:
        return REM_SHA


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
        progress_prcnt_label.configure(text="YimMenu up to date!", text_color=FG_COLOR)
        progressbar.set(1.0)
    elif get_remote_sha256() != get_local_sha256():
        download_button.configure(state="normal")
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} available!", text_color="red"
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
        Thread(target=refresh_download_button).start()
    # if download failed
    except requests.exceptions.RequestException as e:
        progress_prcnt_label.configure(
            text=f"{check_if_dll_is_downloaded()} error: {e}", text_color="red"
        )
        reset_progress_prcnt_label()


# starts the download in a thread to keep the gui responsive
def start_download():
    Thread(target=download_dll, daemon=True).start()


def refresh_inject_button():
    while True:
        for process in psutil.process_iter():
            if process.name() == PROCNAME:
                inject_button.configure(state="normal")
                reset_inject_progress_label()
                return True
            elif process.name() != PROCNAME:
                inject_button.configure(state="disabled")
                inject_progress_label.configure(
                    text=f"Start {PROCNAME}!", text_color="red"
                )
                return False
            else:
                pass


refresh_thread_i = Thread(target=refresh_inject_button, daemon=True)


def refresh_loop_i():
    refresh_thread_i.start()


# Injects YimMenu into GTA5.exe process
def inject_dll(PID):
    if os.path.exists(LOCALDLL):
        inject(PID, LOCALDLL)
    else:
        inject_progress_label.configure(
            text="YimMenu.dll not Downloaded!", text_color="red"
        )
        reset_inject_progress_label()


def find_n_verify_pid():
    global PID
    for process in psutil.process_iter():
        if process.name() == PROCNAME:
            PID = process.pid
    if PID:
        inject_progress_label.configure(
            text=f"GTA.exe [{PID}] found!", text_color=FG_COLOR
        )
        injection_progressbar.set(0.5)
        inject_dll(PID)
        injection_progressbar.set(1.0)
        inject_progress_label.configure(
            text=f"YimMenu injected successfully @ GTA.exe [{PID}]!",
            text_color=FG_COLOR,
        )
        reset_inject_progress_label()

    else:
        inject_progress_label.configure(text=f"GTA.exe not found!", text_color="red")
        reset_inject_progress_label()


def start_injection():
    Thread(target=find_n_verify_pid, daemon=True).start()


def reset_inject_progress_label():
    sleep(3)
    inject_progress_label.configure(text=f"Currently not Injecting", text_color=WHITE)
    injection_progressbar.set(0)


# opens github repo
def open_github(e):
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU")


# label for github repo - author (NV3) - version
copyright_label = ctk.CTkLabel(
    master=root,
    font=CODE_FONT_SMALL,
    text_color=BG_COLOR,
    text="↣ Click Here for GitHub Repo ↢\n⋉ © NV3 ⋊\n{ v1.0.2 }",
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


if check_if_dll_is_downloaded() == "Download":
    tabview.add("Download")
elif check_if_dll_is_downloaded() == "Update":
    tabview.add("Update")


tabview.add("Inject")


# reset progress label
def reset_progress_prcnt_label():
    sleep(3)
    progress_prcnt_label.configure(text="Progress: N/A", text_color=WHITE)
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
    text="Progress: N/A",
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
    download_info.minsize(280, 120)

    download_info_label = ctk.CTkLabel(
        master=download_info,
        text=f'⭐ {check_if_dll_is_downloaded()} YimMenu.dll ⭐\n\nHow-To:\n↦ CLick on ({check_if_dll_is_downloaded()})\n↪ wait to finish\n↪ file in "YMU/dll"-folder',
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
    inject_info.minsize(280, 120)

    inject_info_label = ctk.CTkLabel(
        master=inject_info,
        text="⭐ Inject YimMenu.dll ⭐\n\nHow-To:\n↦ CLick on (Inject YimMenu)\n↪ wait to finish\n↪ YimMenu injected ✅",
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

root.after(0, refresh_loop_i)


if __name__ == "__main__":
    root.mainloop()
