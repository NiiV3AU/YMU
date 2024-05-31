import customtkinter as ctk
from customtkinter import CTkFont
import requests
import os
import hashlib
from threading import Thread
from time import sleep as sleep
import webbrowser

# Colors
BG_COLOR = "#333333"
DBG_COLOR = "#2b2b2b"
FG_COLOR = "#45e876"
BHVR_COLOR = "#36543F"

# Url and Paths
DLLURL = "https://github.com/YimMenu/YimMenu/releases/download/nightly/YimMenu.dll"
DLLDIR = "./dll"
LOCALDLL = "./dll/YimMenu.dll"


# downloads the dll from github and displays progress in a progressbar
def download_dll():
    root.after(0, reset_progress_prcnt_label)
    if not os.path.exists(DLLDIR):
        os.makedirs(DLLDIR)

    try:
        with requests.get(DLLURL, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            progressbar.set(0)
            downloaded_size = 0
            with open(LOCALDLL, "wb") as f:
                for chunk in r.iter_content(chunk_size=65536):  # 64 KB chunks
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    progress = downloaded_size / total_size
                    progressbar.set(progress)
                    progress_prcnt_label.configure(
                        text=f"[Progress: {int(progress*100)}%]"
                    )
                    progress_prcnt_label.update_idletasks()  # Aktualisiere das Label
        # if download successful
        progress_prcnt_label.configure(text="Download successful", text_color=FG_COLOR)

    # if download failed
    except requests.exceptions.RequestException as e:
        progress_prcnt_label.configure(text=f"Download error: {e}", text_color="red")


# starts the download in a thread to keep the gui responsive
def start_download():
    Thread(target=download_dll).start()


# YMU Appearance - currently only dark mode
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


# YMU root - title - minsize - launch size - launch in center of sreen
root = ctk.CTk()
root.title("YMU - YimMenuUpdater")
root.minsize(280, 400)
root.configure(fg_color=DBG_COLOR)
width_of_window = 280
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


# opens github repo
def open_github(e):
    webbrowser.open_new_tab("https://github.com/NiiV3AU/YMU")


# opens latest YimMenu Build for sha256 verify
def open_ghsha256():
    webbrowser.open_new_tab("https://github.com/YimMenu/YimMenu/releases/latest")


# label for github repo - author (NV3) - version
copyright_label = ctk.CTkLabel(
    master=root,
    font=CODE_FONT_SMALL,
    text_color=BG_COLOR,
    text="↣ Click Here for GitHub Repo ↢\n⋉ © NV3 ⋊\n{ v1.0.0 }",
    bg_color="transparent",
    fg_color=DBG_COLOR,
    justify="center",
)
copyright_label.pack(pady=10, fill=None, expand=False, anchor="n", side="top")

copyright_label.bind("<ButtonRelease>", open_github)


# resets progressbar
def reset_progressbar_get_local_sha256_button():
    progressbar_get_local_sha256_button.set(0)


# reads sha256 of YimMenu.dll
def get_sha256():
    def progress_callback(v):
        progressbar_get_local_sha256_button.set(v)

    if not os.path.exists(DLLDIR):
        current_sha_tbox.configure(state="normal")
        progress_callback(0.2)
        current_sha_tbox.delete("0.0", "end")
        progress_callback(0.4)
        current_sha_tbox.configure(text_color="red")
        progress_callback(0.6)
        current_sha_tbox.insert("0.0", "File not Downloaded")
        progress_callback(0.8)
        current_sha_tbox.configure(state="disabled")
        progress_callback(1.0)
        root.after(3000, reset_progressbar_get_local_sha256_button)
    else:

        def read_file_in_chunks(file_object, chunk_size=256000):
            while True:
                data = file_object.read(chunk_size)
                if not data:
                    break
                yield data

        def calculate_sha256_with_progress(filepath, progress_callback):
            total_size = os.path.getsize(filepath)
            bytes_read = 0

            with open(filepath, "rb") as f:
                sha256 = hashlib.sha256()
                for chunk in read_file_in_chunks(f):
                    sha256.update(chunk)
                    bytes_read += len(chunk)
                    progress = bytes_read / total_size
                    progress_callback(progress)  # Update the progress bar

            return sha256.hexdigest()

        current_sha256 = calculate_sha256_with_progress(LOCALDLL, progress_callback)
        current_sha_tbox.configure(state="normal")
        current_sha_tbox.configure(text_color="#DCE4EE")
        current_sha_tbox.delete("0.0", "end")
        current_sha_tbox.insert("0.0", f"{current_sha256}")
        current_sha_tbox.configure(state="disabled")


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
    Thread(target=copyright_label_ani_master).start()


root.after(1000, master_ani_start)

# Download/Update and SHA256 tabs
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

tabview.add("Download/Update")
tabview.add("SHA256")


# reset progress label
def reset_progress_prcnt_label():
    progress_prcnt_label.configure(text="[Progress: N/A]", text_color="#DCE4EE")
    progressbar.set(0)


# open more info for sha256
def open_sha256_info(e):

    sha256_info = ctk.CTkToplevel(root, fg_color=BG_COLOR)
    sha256_info.minsize(280, 220)
    sha256_info_label = ctk.CTkLabel(
        master=sha256_info,
        text="⭐ Compare the SHA256 Strings ⭐\n\nHow-To:\n1. CLick on (Get Build SHA256 ↗)\n↪ opens website\n\n2. Click on (Get local SHA256 ↘)\n↪ SHA256 loads in Textbox\n\n3. Compare both SHA256 Strings\n↪ same = 👍 | different = 👎",
        font=CODE_FONT,
        justify="center",
        text_color=FG_COLOR,
    )
    sha256_info_label.pack(pady=10, padx=10, expand=True, fill="both")


def hover_sha256_mi(e):
    sha256_more_info_label.configure(cursor="hand2")
    sha256_more_info_label.configure(text_color=FG_COLOR)


def normal_sha256_mi(e):
    sha256_more_info_label.configure(cursor="arrow")
    sha256_more_info_label.configure(text_color="#DCE4EE")


sha256_more_info_label = ctk.CTkLabel(
    master=tabview.tab("SHA256"),
    text="↣ Click here for more info ↢",
    justify="center",
    font=CODE_FONT,
)
sha256_more_info_label.pack(
    pady=10,
    padx=10,
    expand=False,
    fill=None,
)


sha256_more_info_label.bind("<ButtonRelease>", open_sha256_info)
sha256_more_info_label.bind("<Enter>", hover_sha256_mi)
sha256_more_info_label.bind("<Leave>", normal_sha256_mi)


def hover_get_ghsha256_button(e):
    get_ghsha256_button.configure(text_color=FG_COLOR)
    get_ghsha256_button.configure(fg_color="#36543F")


def nohover_get_ghsha256_button(e):
    get_ghsha256_button.configure(text_color=BG_COLOR)
    get_ghsha256_button.configure(fg_color=FG_COLOR)


get_ghsha256_button = ctk.CTkButton(
    master=tabview.tab("SHA256"),
    text="Get Build SHA256 ↗",
    command=open_ghsha256,
    fg_color=FG_COLOR,
    hover_color=BHVR_COLOR,
    text_color=BG_COLOR,
    font=SMALL_BOLD_FONT,
    corner_radius=10,
)

get_ghsha256_button.pack(pady=10, padx=5, expand=False, fill=None)

get_ghsha256_button.bind("<Enter>", hover_get_ghsha256_button)
get_ghsha256_button.bind("<Leave>", nohover_get_ghsha256_button)


def hover_get_local_sha256_button(e):
    get_local_sha256_button.configure(text_color=FG_COLOR)
    get_local_sha256_button.configure(fg_color="#36543F")


def nohover_get_local_sha256_button(e):
    get_local_sha256_button.configure(text_color=BG_COLOR)
    get_local_sha256_button.configure(fg_color=FG_COLOR)


def start_sha256_thread():
    Thread(target=get_sha256).start()


get_local_sha256_button = ctk.CTkButton(
    master=tabview.tab("SHA256"),
    text="Get local SHA256 ↘",
    command=start_sha256_thread,
    fg_color=FG_COLOR,
    hover_color=BHVR_COLOR,
    text_color=BG_COLOR,
    font=SMALL_BOLD_FONT,
    corner_radius=10,
)

get_local_sha256_button.pack(pady=10, padx=5, expand=False, fill=None)


get_local_sha256_button.bind("<Enter>", hover_get_local_sha256_button)
get_local_sha256_button.bind("<Leave>", nohover_get_local_sha256_button)
current_dll = ctk.CTkLabel(
    master=tabview.tab("SHA256"),
    font=SMALL_BOLD_FONT,
    text="YimMenu.dll:",
)
current_dll.pack(padx=5, pady=5, expand=False, fill=None)

# current_dll.configure(state="disabled")
current_sha_tbox = ctk.CTkTextbox(
    master=tabview.tab("SHA256"),
    font=CODE_FONT,
    corner_radius=12,
    height=20,
    wrap="char",
    fg_color=DBG_COLOR,
)
current_sha_tbox.pack(padx=5, pady=5, expand=True, fill="both")
current_sha_tbox.insert("0.0", "Click on [Check SHA256]")


progressbar_get_local_sha256_button = ctk.CTkProgressBar(
    master=tabview.tab("SHA256"),
    orientation="horizontal",
    height=8,
    corner_radius=14,
    fg_color=DBG_COLOR,
    progress_color=FG_COLOR,
)
progressbar_get_local_sha256_button.pack(
    pady=5, padx=5, expand=False, fill="x", side="bottom", anchor="s"
)
progressbar_get_local_sha256_button.set(0)


progressbar = ctk.CTkProgressBar(
    master=tabview.tab("Download/Update"),
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
    master=tabview.tab("Download/Update"),
    text="[Progress: N/A]",
    font=CODE_FONT_SMALL,
    height=10,
    text_color="#DCE4EE",
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


# more info for download/update
def open_download_info(e):

    download_info = ctk.CTkToplevel(root, fg_color=BG_COLOR)
    download_info.minsize(280, 120)

    download_info_label = ctk.CTkLabel(
        master=download_info,
        text='⭐ Download or Update YimMenu.dll ⭐\n\nHow-To:\n↦ CLick on (Download/Update)\n↪ wait to finish\n↪ file in "YMU/dll"-folder',
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
    download_more_info_label.configure(text_color="#DCE4EE")


download_more_info_label = ctk.CTkLabel(
    master=tabview.tab("Download/Update"),
    text="↣ Click here for more info ↢",
    justify="center",
    font=CODE_FONT,
)
download_more_info_label.pack(pady=10, padx=10, expand=False, fill=None)


download_more_info_label.bind("<ButtonRelease>", open_download_info)
download_more_info_label.bind("<Enter>", hover_download_mi)
download_more_info_label.bind("<Leave>", normal_download_mi)

download_button = ctk.CTkButton(
    master=tabview.tab("Download/Update"),
    text="Download/Update",
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


if __name__ == "__main__":
    root.mainloop()
