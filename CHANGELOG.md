# Changelog

All notable changes to the YimMenuUpdater (YMU) project will be documented in this file.

## [v1.1.11] - 2026-09-07

### Systems Engineering, Antivirus Hardening & UX Polish

> Eliminates antivirus false positives via native Win32 process enumeration, hardens handle lifecycles and UAC operations, migrates DLL storage to %LOCALAPPDATA%, adds a dedicated maintenance suite (cache cleaner, bulk Lua toggling, FSL detection), handles locked DLL files gracefully, and introduces refreshed Lucide icons with comprehensive UI/UX refinements.

#### Features & Improvements

- Eliminated antivirus false-positive alerts by replacing `psutil` with native Win32 `ctypes` process snapshots.
- Pruned external dependencies down to PySide6, Requests, and Pyinjector; implemented native regex version parsing.
- Migrated downloaded DLL storage from `%APPDATA%\YMU\dll` to `%LOCALAPPDATA%\YMU\dll` with an explicit bootstrap migration on startup.
- Added asynchronous in-place UAC elevation to edit or remove `-nobattleye` in `commandline.txt` for protected game installations without freezing the Qt GUI thread or restarting YMU.
- Added a Maintenance card in Settings featuring a smart pointer cache cleaner and direct access to YimMenu/YimMenuV2 logs.
- Added one-click Lua bulk actions ("Disable All (Safe Mode)" and "Enable All") in Settings, consolidated natively in `lua_manager`.
- Added an FSL (Free Save Launcher) status indicator in Settings detecting `WINMM.dll` or `version.dll` with an UnknownCheats shortcut.
- Added edition-aware UI separation for YimMenu (Legacy) vs YimMenuV2 (Enhanced): visually dims unsupported options with 40% opacity, sets forbidden cursors, appends `(Legacy only)` badges, and dynamically updates folder/log button labels.
- Upgraded all icons across the application to modern Lucide icons, including a custom syringe icon for the Inject tab.
- Harmonized step-by-step help dialogs with left-aligned centered text and clear `[Button]` bracket notation.
- Added explicit Windows file lock detection (`FileLockedException` for WinError 5/32), notifying users cleanly when `YimMenu.dll` is locked by a running GTA V process.
- Maintained 100% translation key parity across all 15 supported languages, adding missing notification keys and fixing encoding artifacts in German translations.

#### Fixes

- Hardened Win32 API calls with explicit 64-bit argument and return type definitions across `kernel32`, `shell32`, and `psapi`.
- Eliminated kernel handle leaks by wrapping Toolhelp32 snapshots, elevated process handles, and single-instance mutex retry handles in strict `try...finally` blocks.
- Secured elevated UAC helper commands using PowerShell `-EncodedCommand` with `-LiteralPath`, eliminating shell metacharacter injection vectors.
- Eliminated Qt event loop re-entrancy risks by removing legacy `QApplication.processEvents()` calls in favor of direct widget repaints.
- Fixed a memory leak in `AnimatedButton` by reusing a persistent `QPropertyAnimation` instance instead of instantiating new objects on every animation trigger.
- Protected internal settings cache from mutation pollution with dedicated thread locking and deep copies.
- Corrected Qt object parenting for `QButtonGroup` and `QTimer` instances across `MainWindow` and `SettingsPage`.
- Fixed horizontal layout overflow and unwanted scrollbars in the Settings page.
- Optimized Nuitka compilation: unpacked binaries cache in LocalAppData and pruned over 20 MB of unneeded dependencies (Qt translations, QtNetwork, Direct2D, unused image decoders, PDF/TLS plugins) while Python's native OpenSSL stack handles all HTTPS traffic.

## [v1.1.10] - 2026-09-03

### In-App Restart Hotfix

> Targeted hotfix resolving an issue where restarting YMU from within the application caused SSL and network connection failures.

#### Fixes

- Purged `NUITKA_*` environment variables before spawning new instances in `restart_application` and `restart_as_admin`.
- Prevented newly spawned child processes from inheriting expiring temporary payload paths during in-app restarts, which previously caused missing SSL DLLs (`libcrypto-3.dll`) and network request failures.
- Hardened subprocess restart parameters and PID handover on Windows.

## [v1.1.9] - 2026-09-03

### Quality of Life & Precision

> Real-time in-memory module verification, auto-close after successful injection, audio feedback chimes, one-click -nobattleye commandline helper, full keyboard navigation & focus overhaul, and hardened notification lifecycle.

#### Features & Improvements

- Added real-time in-memory module verification for injected DLLs to confirm successful injection in process memory.
- Implemented automatic application close option after successful injection.
- Added audio feedback chimes for successful actions and notifications.
- Introduced one-click BattlEye disabling toggle modifying `commandline.txt` with `-nobattleye`.
- Overhauled keyboard navigation, focus traversal, and accessibility across all tabs and dialogs.
- Symmetrically aligned notification margins and hardened toast stack lifecycle management.
- Refactored project architecture into clean `core` and `ui` packages.
- Achieved 100% translation parity across 15 supported languages.

#### Fixes

- Resolved injection false-positive crash detections.
- Handled mutex release latency and process restart edge cases in development environments.
- Improved download stream integrity, rate limiting, and network retry handling.

## [v1.1.8] - 2026-07-21

### Reliability & Clarity

> Fixes injection failing when your install path contains accented or non-ASCII characters (e.g. "Müller" or a Cyrillic user name), plus plain-language injection errors with one-click fixes, a non-blocking BattlEye warning, a pre-injection DLL check, and a Start button that recovers when a launch never completes.

#### Features & Improvements

- Added plain-language injection diagnostics with one-click fixes (re-download DLL or troubleshooting guides) instead of generic error codes.
- Introduced non-blocking BattlEye warning dialog offering options to proceed, learn how to disable BattlEye, or cancel.
- Added pre-injection validation verifying that the DLL is a valid 64-bit PE binary before attempting injection.
- Added Korean (`ko_KR`) localization and restructured Chinese translations (`zh_CN`, `zh_TW`).
- Added a 60-second recovery timeout that resets and re-enables the "Start GTA" button if the game fails to launch.
- Enriched logging with a UTF-8 console handler, startup admin status, and detailed injection diagnostics.

#### Fixes

- Resolved injection failure when the installation path contains accented or non-ASCII characters (bypassing Pyinjector's ANSI `LoadLibraryA` limitation via 8.3 short paths or ASCII staging).

## [v1.1.7] - 2026-07-08

### Compatibility, Customizability & Bugfixes

> GTA V Enhanced is reliably detected again and launches through YMU, complemented by a Legacy/Enhanced switch, custom install paths, custom DLL injection, remembered selections, and a refreshed light theme.

#### Features & Improvements

- Added edition switcher toggle between GTA V Legacy and GTA V Enhanced with per-mode configurations and injection targets.
- Added support for custom GTA V installation directories and custom DLL file selection.
- Persisted user choices for launcher and DLL dropdown selections across application restarts.
- Redesigned light theme with an elevated color palette, refined hierarchy, and soft card drop-shadows.
- Switched to passive update checks pointing to GitHub releases, replacing the bundled self-updater.
- Migrated project packaging and dependency management to `uv` with Python 3.12.
- Implemented thread-safe configuration store (`YmuConfig`) using atomic file writes and v1 configuration migration.
- Moved background tasks to `QThreadPool` with an exclusive-task guard.

#### Fixes

- Restored reliable detection and launching for GTA V Enhanced Edition.
- Prevented elevation loop when running into Access Denied errors.
- Closed race condition in update checks when switching editions.

## [v1.1.6] - 2025-12-17

### Localization, Performance & Bugfixes

> Added full support for GTA V Enhanced Edition, support for 12 languages, and migrated to Nuitka for a significantly smaller and faster executable.

#### Features & Improvements

- Migrated compiler toolchain from PyInstaller to Nuitka, reducing executable binary size by ~50% and improving launch performance.
- Added full support for GTA V Enhanced Edition, including process detection and registry lookup.
- Implemented dynamic localization engine supporting 12 languages with remote translation fetching from GitHub.
- Added hot-swapping language support with dynamic UI resizing and "Restart Now" prompts.
- Added standardized User-Agent header containing the repository URL to all network requests.

#### Fixes

- Resolved self-restart failures and icon/SSL extraction errors previously caused by PyInstaller temp folders.
- Fixed FSL UnknownCheats thread hyperlink in the interface.
- Replaced hardcoded string constants in update checking routines.
- Hardened DLL injection logic and admin elevation restart flows.

## [v1.1.5] - 2025-08-31

### The Modern UI Update

> Complete rewrite from the ground up with a modern PySide6 architecture, brand-new user interface, non-blocking notifications, and initial GTA V Enhanced Edition support.

#### Features & Improvements

- Completely overhauled application from CustomTkinter to a modular, object-oriented PySide6 (Qt) architecture.
- Designed brand-new modern interface with custom widgets, smooth animations, and refined layout spacing.
- Implemented asynchronous non-blocking toast notification system.
- Added multithreaded `WorkerManager` to run downloads and background tasks without locking the GUI.
- Added preliminary support for GTA V Enhanced Edition via YimMenuV2.
- Cleaned codebase to achieve zero linting and static analysis errors.

## [v1.1.4] - 2024-10-12

### Buttons & Information Overhaul

> Added direct repository and UC-thread buttons in the Download tab, expanded informational help dialogs, and added a top banner notice.

#### Features & Improvements

- Added quick-access buttons in the Download tab linking directly to the YimMenu GitHub repository and UnknownCheats thread.
- Added prominent animated banner label at the top of the interface warning users to disable BattlEye.
- Updated and enlarged "More Info" dialog windows across both the Download and Inject tabs.
- Polished button hover interactions and status messages.

## [v1.1.3] - 2024-09-01

### Lua Script Manager

> Introduced an interactive Lua script manager in the Settings tab to monitor installed scripts, open script folders, and discover new community extensions.

#### Features & Improvements

- Added Lua script manager in the Settings tab displaying counts and filenames of installed scripts.
- Visual status indicators differentiating active (green) and disabled (yellow) Lua scripts.
- Clickable script labels to immediately open the local Lua scripts directory in Windows Explorer.
- Added "Refresh" button to reload installed Lua scripts dynamically.
- Repositioned the "Discover Luas" shortcut button below the newly introduced script manager.
- Added informative "Lua Settings Info" helper dialog window.

## [v1.1.2] - 2024-08-29

### Progress Bar Bugfix

> Targeted bugfix resolving a UI freeze where the progress bar hung during DLL downloads.

#### Fixes

- Fixed progress bar freezing during DLL downloads by properly updating progress states.
- Cleaned up dependency specifications and internal version strings.

## [v1.1.1] - 2024-08-10

### Launcher Path Caching Bugfix

> Resolved launcher detection and Rockstar Games Launcher path resolution failures caused by improper caching.

#### Fixes

- Removed erroneous `@cache` decorators from `get_launcher()` and `get_rgl_path()` to ensure dynamic path and selection evaluation.
- Updated GitHub Actions release workflows.

## [v1.1.0] - 2024-07-26

### Epic Games Launcher Compatibility

> Resolved launch and startup issues for users running Grand Theft Auto V through the Epic Games Store.

#### Fixes

- Fixed game launch failures when using the Epic Games Store launcher option.
- Improved error handling during launcher process initialization.

## [v1.0.9] - 2024-07-13

### Logging System & Performance Caching

> Added a dedicated logging system for diagnostics and troubleshooting, along with temporary response caching for improved performance.

#### Features & Improvements

- Added file and console logging system (`ymu/ymu.log`) to facilitate debugging and issue reporting.
- Integrated `requests_cache` with an SQLite backend to cache network requests and reduce redundant GitHub API queries.
- Implemented automatic temporary cache deletion upon application exit.
- Added issue templates and updated GitHub bug report and feature request URLs.
- Standardized UI section headers and dialog styling.

## [v1.0.8] - 2024-07-06

### Troubleshooting & Community Integration

> Added dedicated troubleshooting and feedback buttons in the Settings tab along with fixes for Rockstar Games Launcher detection.

#### Features & Improvements

- Added troubleshooting shortcut buttons in the Settings tab: "Report a Bug", "Request a Feature", and "Join Discord".
- Created GitHub issue templates for structured bug reports and feature suggestions.
- Refined button hover assets and light theme asset variations.

#### Fixes

- Fixed Rockstar Games Launcher detection and registry query handling.

## [v1.0.7] - 2024-07-05

### Launcher Protocol Redesign

> Reworked GTA V launch mechanisms with direct Steam, Epic Games, and Rockstar Games Launcher detection, replacing desktop shortcut scanning.

#### Features & Improvements

- Replaced desktop `.url` shortcut scanning with direct launcher protocols (Steam URI `steam://run/271590`, Epic Games URI, and Rockstar Games Launcher registry path lookup).
- Added launcher dropdown selection menu to specify the game platform.
- Increased main window height to 440px to accommodate launcher controls.
- Added automated GitHub Actions release workflow.

#### Fixes

- Added clear error feedback when Rockstar Games Launcher installation cannot be found.

## [v1.0.6] - 2024-07-02

### Game Launching & Layout Polish

> Introduced a Start GTA 5 launcher button in the Inject tab along with structured card frames, border highlights, and folder reorganization.

#### Features & Improvements

- Added "Start GTA 5" button to the Inject tab to initiate the game directly from YMU.
- Reorganized Settings and Inject tabs into clean card frames with interactive hover borders.
- Automatically migrated legacy `dll/` directory to `ymu/dll/`.
- Added combined info dialog covering both game launching and DLL injection.

## [v1.0.5] - 2024-06-21

### Debug Console Toggle & Release Browser

> Added an external debug console switch in Settings and a button to open release notes directly in the browser.

#### Features & Improvements

- Added "Enable External Debug Console" toggle in Settings, modifying YimMenu's `settings.json` directly.
- Added "Open in Browser" button in the Changelog window to open GitHub releases in the default web browser.
- Polished switch button colors, hover states, and asset paths.

## [v1.0.4] - 2024-06-16

### Theme Selection & Lua Auto-Reload

> Introduced light and dark theme selection, hover animations for interactive controls, and an auto-reload Lua scripts toggle.

#### Features & Improvements

- Added theme selection supporting both Dark and Light modes.
- Added "Enable Auto Reload for Lua-Scripts" toggle modifying YimMenu configuration.
- Added "Discover Luas" shortcut button in the Settings tab.
- Added interactive border and color transitions when hovering over interactive elements.
- Refined splash screen loading sequence.

## [v1.0.3] - 2024-06-11

### Self-Updater & UI Polish

> Introduced the built-in self-updater in the new Settings tab, centered dialog windows, and improved hover feedback.

#### Features & Improvements

- Introduced in-app self-updater located in a newly created Settings tab.
- Added "Open YimMenu Folder" shortcut button in Settings.
- Improved injection button state handling and user feedback.
- Centered all popup windows (`CTkToplevel`) on screen with instant focus.
- Refined accent colors across themes.

## [v1.0.2] - 2024-06-09

### YimMenu Changelog & Tab Consolidation

> Integrated the YimMenu changelog viewer, consolidated the Download and Update tabs, and added a splash screen and application icon.

#### Features & Improvements

- Consolidated separate "Download" and "Update" tabs into a unified "Download/Update" tab.
- Removed legacy SHA256 tab in favor of automated hash verification.
- Integrated YimMenu changelog viewer with clickable dialog.
- Added startup splash screen and official application icon (`ymu.ico`).
- Added initial `requirements.txt` specifying project dependencies.

#### Fixes

- Fixed process termination issue where YMU did not close completely on exit.

## [v1.0.1] - 2024-06-02

### DLL Injection & Dedicated Inject Tab

> Added process injection support using PyInjector with a dedicated Inject tab to inject YimMenu directly into Grand Theft Auto V.

#### Features & Improvements

- Added dedicated "Inject" tab in the GUI.
- Integrated `pyinjector` for direct DLL injection into running `GTA5.exe` processes.
- Added injection progress indicator and instructional "How-To" injection guide dialog.

## [v1.0.0] - 2024-05-31

### Initial Release

> Initial release of YimMenuUpdater featuring automated DLL downloads, progress tracking, and SHA-256 integrity verification.

#### Features

- Automated download of nightly `YimMenu.dll` binaries from GitHub releases.
- Dedicated SHA-256 verification tab to compute local DLL hash and compare against official release checksums.
- Real-time download progress bar and status percentage indicators.
- Dark-themed CustomTkinter graphical interface.
