# YimMenuUpdater (YMU)

The modern, all-in-one launchpad for YimMenu. **Always updated, always ready.**

<div align="center">

[![Website](https://img.shields.io/badge/Website-ymu.pages.dev-gray?style=for-the-badge&logo=cloudflare&logoColor=white&labelColor=F38020)](https://ymu.pages.dev/)
[![Latest Release](https://img.shields.io/github/v/release/NiiV3AU/YMU?style=for-the-badge&logo=github&logoColor=white&labelColor=181717&color=gray)](https://github.com/NiiV3AU/YMU/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/NiiV3AU/YMU/total?style=for-the-badge&logo=github&logoColor=white&labelColor=181717&color=gray)](https://github.com/NiiV3AU/YMU/releases)
[![VirusTotal Scan](https://img.shields.io/badge/VirusTotal-View_Scan_Report-gray?style=for-the-badge&logo=virustotal&logoColor=white&labelColor=394EFF)](https://www.virustotal.com/gui/file/7c09b8c3c2031536fcdb6b8cdeb74c8745fa9221c6559a7f87b225a3d03d6ecc)

![YMU Showcase](https://github.com/user-attachments/assets/a017affb-f48f-44fe-be75-222d2e3477dc?raw=true)

</div>

[YMU](https://ymu.pages.dev/) is a sleek and powerful launcher for YimMenu that handles everything for you. From downloading the latest DLLs to injecting them into the game, YMU ensures a stable and seamless experience with a clean and intuitive user interface.

---

## ✨ Features

- **Dual-Edition Support:** Seamlessly switch between GTA V Legacy (YimMenu) and Enhanced (YimMenuV2) with instant auto-detection.
- **Automated DLL Management:** Download and update YimMenu with a single click, protected by SHA-256 integrity verification.
- **Smart Safety Checks:** Automatic 64-bit architecture validation and non-blocking BattlEye service detection with clear risk guidance.
- **Integrated Game Launcher:** Start GTA V directly via Steam, Epic Games, Rockstar Games Launcher, or a custom directory.
- **Resilient Injection Engine:** Built-in UTF-8 and ANSI path sanitization ensures reliable injection even on Windows accounts with special characters or accents.
- **Lua Script Manager:** Easily enable, disable, and organize scripts on the fly, with direct access to scripts folders and auto-reload settings.
- **Multi-Language Support:** Available in 15 languages with over-the-air translation updates directly within the app.
- **Modern UI/UX:** A clean, responsive interface featuring both dark and light modes.

---

## 🛡️ Safety & Transparency

- **Full source, in the open:** Every line of YMU lives here on GitHub. Don't just trust it; read it, or build the `.exe` yourself and compare.
- **Verified downloads:** YMU fetches YimMenu DLLs only from their official repositories and verifies each download's SHA-256 against the publisher's published hash before it is used.
- **Microsoft SmartScreen:** Because YMU isn't code-signed, a fresh release may trigger a SmartScreen prompt until it builds up enough reputation. You can always cross-check the published `YMU.exe` hash against its VirusTotal report.

> [!WARNING]
> **On third-party menus:** A matching checksum proves you received exactly what the publisher posted. It cannot prove that the publisher's source is, and forever stays, safe. YimMenu is a separate project, and a compromised upstream or supply-chain attack is outside YMU's control. Use mods at your own risk.

---

## 🚀 Getting Started

Download and run `YMU.exe` directly from the latest release. No installer required.

| [Download YMU.exe (Latest Release)](https://github.com/NiiV3AU/YMU/releases/latest) |
| :---------------------------------------------------------------------------------: |

---

## 🖼️ Screenshots

### Dark Theme

<div align="center">
  <img src="screenshots/Download.webp" alt="YMU Dark Theme: Download" width="32%"/>
  <img src="screenshots/Launch.webp" alt="YMU Dark Theme: Inject" width="32%"/>
  <img src="screenshots/Settings.webp" alt="YMU Dark Theme: Settings" width="32%"/>
</div>

### Light Theme

<div align="center">
  <img src="screenshots/Download_Light.webp" alt="YMU Light Theme: Download" width="32%"/>
  <img src="screenshots/Launch_Light.webp" alt="YMU Light Theme: Inject" width="32%"/>
  <img src="screenshots/Settings_Light.webp" alt="YMU Light Theme: Settings" width="32%"/>
</div>

---

## 🖼️ Project Evolution

<details>
<summary><b>A look back at older versions & the full changelog</b></summary>

### v1.0.9

<div align="center">
  <img src="https://github.com/user-attachments/assets/a8298b7d-ee3b-4314-a1f8-4a005c23f2f6" alt="YMU v1.0.9" width="32%"/>
</div>

### v1.0.3

<div align="center">
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/5cf46352-0bdb-442f-b1fa-951d3ba1d35b" alt="YMU v1.0.3 Download/Update Tab" width="32%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/f717a2b8-b9c6-4225-ad05-b9d3ff1204e3" alt="YMU v1.0.3 Inject Tab" width="32%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/07c4c61d-41a2-47f7-9256-f81337b8512d" alt="YMU v1.0.3 Settings Tab" width="32%"/>
</div>

### v1.0.2

<div align="center">
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/2f138a6a-21be-4cde-9a10-4057b186302b" alt="YMU v1.0.2 Download/Update Tab" width="22%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/5b4b05f5-90c7-42d4-9c58-791a71b48cdb" alt="YMU v1.0.2 Inject Tab" width="22%"/>
</div>

### v1.0.1

<div align="center">
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/b14342a3-af81-4da0-b863-df2e264bce5f" alt="YMU v1.0.1 Download Tab" width="24%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/86a307f0-8b8f-4b8a-931d-fa855a70c365" alt="YMU v1.0.1 Update Tab" width="24%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/60834c8d-1c4e-42e6-90a5-062c0e8f9546" alt="YMU v1.0.1 SHA256 Tab" width="24%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/b16bedc6-ca12-4d0e-9c96-ec9e73f1c978" alt="YMU v1.0.1 Inject Tab" width="24%"/>
</div>

### v1.0.0

<div align="center">
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/6d1635a2-0596-445d-bcad-752cf6c0f904" alt="YMU v1.0.0 Download/Update Tab" width="38%"/>
  <img src="https://github.com/NiiV3AU/YMU/assets/86131759/e98c1a92-0bff-45d2-a2a2-218fa32fa416" alt="YMU v1.0.0 SHA256 Tab" width="38%"/>
</div>

---

### Full Changelog

- **NEW** in `v1.1.9` ↦ ⚡ **Quality of Life & Precision:** Real-time in-memory module verification, auto-close after successful injection, audio feedback chimes, one-click `-nobattleye` commandline helper, full keyboard navigation & focus overhaul, and hardened notification lifecycle.
- **NEW** in `v1.1.8` ↦ 🛡️ **Reliability & Clarity:** Fixed injection failing when the install path contains accented or non-Latin characters (e.g. `Müller` or a Cyrillic user name), plus plain-language injection errors with one-click fixes, a non-blocking BattlEye warning, a pre-injection DLL check, and a Start button that recovers when a launch never completes.
- **NEW** in `v1.1.7` ↦ ⚙️ **Customizability & Fixes:** Reliable GTA V Enhanced detection with a Legacy/Enhanced switch, custom game-path and custom-DLL support, remembered launcher/DLL selections, and a refreshed light theme.
- **NEW** in `v1.1.6` ↦ 🌍 **Localization & Performance:** Added full support for GTA V Enhanced Edition, support for 12 languages, and migrated to Nuitka for a significantly smaller and faster executable.
- **NEW** in `v1.1.5` ↦ 💥 **The Modern UI Update:** Complete rewrite from the ground up with a professional architecture, a brand new user interface, and major UX improvements.
- **NEW** in `v1.1.4` ↦ added Buttons (YimMenu GitHub Repo & FSL's UC-Thread) in Download Tab + updated "more info"-Windows in Download- & Inject-Tab
- **NEW** in `v1.1.3` ↦ New Lua list in Settings-Tab
- **NEW** in `v1.1.2` ↦ fixed progressbar freezing
- **NEW** in `v1.1.0` & `v1.1.1` ↦ Small bug fixes
- **NEW** in `v1.0.9` ↦ Log-System (Debugger) for better troubleshooting (PATH:ymu/ymu.log) + Caching for better performance added
- **NEW** in `v1.0.8` ↦ New Buttons in Settings-Tab for Troubleshooting
- **NEW** in `v1.0.7` ↦ Reworked code for Starting GTA5
- **NEW** in `v1.0.6` ↦ New "Start GTA5"-Button in Inject-Tab + visual updates in Inject and Settings-Tab
- **NEW** in `v1.0.5` ↦ New "Debug Console"-Switch in Settings-Tab + "Open in Browser"-Button in Changelog Window
- **NEW** in `v1.0.4` ↦ GUI: Theme selection (light & dark) + Settings-Tab: auto reload all lua scripts (YimMenu Config)
- **NEW** in `v1.0.3` ↦ Self-Updater in new Settings-Tab + small GUI changes and code improvements
- **NEW** in `v1.0.2` ↦ Changelog of YimMenu in Download/Update-Tab
- **NEW** in `v1.0.1` ↦ Injection in the new Inject-Tab

</details>

---

## 📦 Building from Source

<details>
<summary><b>Click to expand instructions for developers</b></summary>
  
### First things first — get the source

| [Download Source Code](https://github.com/NiiV3AU/YMU/archive/refs/heads/main.zip) |
| :--------------------------------------------------------------------------------: |

### Set up the environment

YMU uses [**uv**](https://docs.astral.sh/uv/) for Python and dependency management. From the project root, a single command installs the right Python (`3.12`), every runtime dependency, **and** the build toolchain (Nuitka lives in the `dev` group):

```bash
uv sync
```

That's it, no manual package installs. For reference, `uv sync` pulls in [PySide6](https://pypi.org/project/PySide6/), [requests](https://pypi.org/project/requests/), [psutil](https://pypi.org/project/psutil/), [pyinjector](https://pypi.org/project/pyinjector/), [pywin32](https://pypi.org/project/pywin32/), and [packaging](https://pypi.org/project/packaging/) as runtime dependencies, plus [Nuitka](https://pypi.org/project/Nuitka/) for building.

> **Not using uv?** Dependencies are declared in `pyproject.toml`, so plain pip works as well:
> `python -m venv .venv && .venv\Scripts\activate`, then install the runtime dependencies and `pip install nuitka` to build.

### Run from source

```bash
uv run python src/main.py
```

### Creating the Executable (.exe)

This project uses **Nuitka** (instead of PyInstaller) to create a high-performance, compact executable. From the project root, run:

```bash
uv run python -m nuitka --onefile --standalone --enable-plugin=pyside6 --windows-icon-from-ico=src/assets/icons/ymu.ico --include-data-dir=src/assets=assets --include-data-dir=src/ui/styles=ui/styles --windows-console-mode=disable --assume-yes-for-downloads --output-dir=dist --output-filename=YMU.exe src/main.py
```

This creates `YMU.exe` in the `dist` folder.

**Command Breakdown:**

- **`--onefile`**: Bundles everything into a single `.exe` file.
- **`--standalone`**: Includes all required libraries and dependencies so no external Python environment is needed.
- **`--enable-plugin=pyside6`**: Optimizes the build for Qt/PySide6.
- **`--windows-console-mode=disable`**: Prevents the console window from opening in the background.
- **`--windows-icon-from-ico`**: Embeds the application icon into the executable.
- **`--include-data-dir`**: Bundles the application `assets` and UI stylesheets (`src/ui/styles`).
- **`--assume-yes-for-downloads`**: Lets Nuitka fetch its C toolchain non-interactively.

> The official release build (see `.github/workflows/ymu_manual_release.yaml`) runs the same command with extra flags that stamp version/company metadata onto the `.exe`.

</details>

---

## ⭐ Support the Project

> [!IMPORTANT]
> **Show your support by giving this Project a ⭐. Thanks <3!**

---

## Disclaimer

> [!WARNING]
> Use this project for educational purposes only and use it at your own risk.

> [!CAUTION]
> I am not liable or responsible for any direct or indirect consequences that may result from the use of YMU or YimMenu.

---

## Credits

| **Core & Vision** | [**@xesdoog**](https://github.com/xesdoog) (Early Development)                                                      |
| :---------------- | :------------------------------------------------------------------------------------------------------------------ |
| **Localization**  | [**@TommyLam120**](https://github.com/TommyLam120) (zh_TW)                                                          |
| **Menu**          | [**YimMenu**](https://yim.gta.menu/)                                                                                |
| **Logo**          | [**Made with Figma**](https://figma.com)                                                                            |
| **Icons**         | [**Feather**](https://feathericons.com/)                                                                            |
| **Fonts**         | [**Manrope**](https://fonts.google.com/specimen/Manrope) & [**JetBrains Mono**](https://www.jetbrains.com/lp/mono/) |
