# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-10-22

### Added

- Full Right-to-Left (RTL) layout support, automatically mirroring interface orientation and navigation for RTL locales.
- Complete Arabic (`ar_SA`) translation with gaming-appropriate terminology, expanding YMU to 16 supported languages.
- Direct keyboard editing, copy/paste, and auto-quote-stripping in custom GTA V and DLL path inputs.
- Bundled open-source license notices (`THIRD-PARTY-NOTICES.md`) and integrated offline license viewer in the new About dialog.
- Animated page transitions and a sliding sidebar indicator that follows the active section.

### Changed

- Replaced external injection dependency (`pyinjector`) with native Windows Win32 injection, supporting non-ASCII/Unicode paths (CJK, Cyrillic, Umlauts) and displaying exact error codes.
- Redesigned Settings layout with a balanced grid, unified 44px control sizing, and improved visual hierarchy.
- Modernized typography with the bundled Rubik typeface across all dialogs and controls.
- Updated bundled Lucide icon pack to v1.52.0 with refreshed action icons.
- Warn when legacy `version.dll` is detected in the game folder, advising to replace it with `WINMM.dll`.
- Startup automatically cleans up obsolete temporary runtime directories from previous versions in `%LOCALAPPDATA%\YMU`.
- Significantly reduced standalone executable size by pruning unused Qt modules and image plugins from the build bundle.

### Fixed

- Fixed premature success reporting on truncated or interrupted downloads lacking Content-Length headers.
- Fixed process module enumeration errors during injection verification when the game is dynamically loading libraries.
- Fixed application exit coordination and event filter lifecycle to ensure clean shutdown without `atexit` errors or hanging background workers.
- Fixed BattlEye toggle file-write safety, preventing `commandline.txt` truncation or character corruption across all text encodings.
- Fixed notification toasts overflowing the window or clipping content in verbose languages.
- Fixed configuration loading to reliably handle UTF-8 BOM signatures and malformed values without resetting settings.

### Security

- Upgraded bundled urllib3 dependency to >=2.8.0 to mitigate GHSA-gh4c-6fx4-qh6g (CVE-2026-97688) and GHSA-vxq7-64xx-v4gw (CVE-2026-97689).

## [1.1.11] - 2026-09-07

### Added

- Maintenance section in Settings with an offset cache cleaner and direct access to game log files.
- One-click bulk actions to enable or disable all Lua scripts (Safe Mode).
- Status indicator in Settings detecting FSL installations.
- Clear visual distinction between YimMenu (Legacy) and YimMenuV2 (Enhanced), disabling options not supported by the active edition.
- Modern Lucide icon pack across the entire application.
- Friendly notification when `YimMenu.dll` cannot be overwritten because GTA V is currently running.
- In-place administrator prompt when editing `-nobattleye` in protected game folders, without freezing the GUI or restarting YMU.

### Changed

- Moved downloaded DLL storage to `%LOCALAPPDATA%\YMU\dll` (automatically migrated on first launch).
- Replaced external process inspection with native Windows APIs, significantly reducing antivirus false positives.
- Streamlined dependencies to keep the application lightweight.
- Improved layout and text clarity in all step-by-step help dialogs.

### Fixed

- Fixed an animation memory leak on interactive buttons.
- Fixed rare UI freezing when launching external tools.
- ~~Optimized build packaging to prune over 20 MB of unneeded dependencies.~~ _(Note: Exclusion syntax was non-functional in v1.1.11; will be resolved in v1.2.0)_

### Security

- Secured background administrator commands against command-injection edge cases.

## [1.1.10] - 2026-09-03

### Fixed

- Fixed network and SSL connection errors that occurred when restarting YMU from within the application (e.g. after changing languages).

## [1.1.9] - 2026-09-03

### Added

- Real-time injection verification confirming that the DLL is actively loaded in GTA V process memory.
- Option to automatically close YMU once injection completes successfully.
- Audio feedback chimes for successful downloads and injections.
- One-click toggle in Settings to automatically add or remove `-nobattleye` in `commandline.txt`.
- Full keyboard navigation support and focus indicators across all tabs and dialogs.

### Changed

- Reorganized project internals into modular core and UI packages.
- Updated all 15 supported languages for complete feature parity.

### Fixed

- Fixed false-positive crash reports during injection.
- Improved network download reliability and retry handling on unstable connections.
- Fixed notification toast alignment and stacking behavior.

## [1.1.8] - 2026-07-21

### Added

- Plain-language injection diagnostics with one-click action buttons (e.g. re-download DLL or open troubleshooting help) instead of technical error codes.
- Warning dialog when BattlEye is detected, explaining how to proceed or disable it.
- Pre-injection file integrity check to ensure the downloaded DLL is complete and valid.
- Korean (`ko_KR`) translation and improved Simplified/Traditional Chinese localizations.
- Automatic 60-second timeout that re-enables the "Start GTA" button if the game fails to open.

### Fixed

- Fixed injection failures when GTA V is installed in a folder path containing accented, umlaut, or non-ASCII characters (such as Cyrillic or special user folder names).

## [1.1.7] - 2026-07-08

### Added

- Edition switcher allowing seamless toggling between GTA V Legacy and GTA V Enhanced with independent settings.
- Support for custom GTA V installation folders and manual DLL file selection.
- Settings persistence: Launcher choices and dropdown selections are remembered across restarts.
- Refreshed light theme with improved contrast and visual hierarchy.

### Changed

- Replaced the external self-updater with a passive update checker notifying of new GitHub releases.
- Configuration system updated to use atomic file saves to prevent corrupted settings.

### Fixed

- Fixed detection and launch issues for GTA V Enhanced Edition.
- Prevented infinite administrator elevation prompts on permission errors.
- Fixed rare race conditions when switching game editions during an update check.

## [1.1.6] - 2025-12-17

### Added

- Support for GTA V Enhanced Edition, including automatic game process detection and registry discovery.
- Multilingual support for 12 languages with in-app language switching and OTA translation updates.

### Changed

- Switched build system to Nuitka, cutting executable size in half and accelerating startup time.

### Fixed

- Fixed application restart failures and temporary file extraction errors.
- Fixed broken community links in the interface.
- Improved injection stability and administrator elevation handling.

## [1.1.5] - 2025-08-31

### Added

- Brand-new modern Qt (PySide6) interface featuring smooth animations, redesigned controls, and card layouts.
- Non-blocking toast notification system for alerts and status messages.
- Background task manager ensuring downloads and checks never freeze the interface.
- Initial preview support for GTA V Enhanced Edition (YimMenuV2).

### Changed

- Completely rewrote the codebase from CustomTkinter to PySide6 for superior responsiveness and native feel.

## [1.1.4] - 2024-10-12

### Added

- Direct quick-access buttons to the YimMenu GitHub repository and UnknownCheats community thread in the Download tab.
- Notice banner at the top of the window reminding users about BattlEye requirements.
- Expanded and clarified "More Info" help dialogs across Download and Inject tabs.

### Changed

- Polished button hover states and status messages.

## [1.1.3] - 2024-09-01

### Added

- Interactive Lua script manager in Settings to view installed scripts, active counts, and filenames.
- Visual status indicators for active (green) and disabled (yellow) Lua scripts.
- One-click shortcut to open the local Lua scripts directory directly in Windows Explorer.
- "Refresh" button to re-scan installed Lua scripts without restarting YMU.
- Lua settings information dialog explaining how script loading works.

## [1.1.2] - 2024-08-29

### Fixed

- Fixed an issue where the progress bar froze during DLL downloads.

## [1.1.1] - 2024-08-10

### Fixed

- Fixed game launch failures where changes to selected launchers or Rockstar Games Launcher paths were not detected.

## [1.1.0] - 2024-07-26

### Fixed

- Fixed game launching for GTA V installations on the Epic Games Store.
- Improved error handling when initializing launcher processes.

## [1.0.9] - 2024-07-13

### Added

- Diagnostic logging system (`ymu/ymu.log`) to assist with troubleshooting and support requests.
- Network request caching to reduce unnecessary GitHub API calls and speed up checks.
- Automatic cleanup of temporary network caches upon exit.

### Changed

- Standardized section headers and dialog styling across the interface.

## [1.0.8] - 2024-07-06

### Added

- Support and community shortcut buttons in Settings: "Report a Bug", "Request a Feature", and "Join Discord".

### Changed

- Refined button hover styling and light theme assets.

### Fixed

- Fixed Rockstar Games Launcher detection from the Windows registry.

## [1.0.7] - 2024-07-05

### Added

- Launcher dropdown to select your platform (Steam, Epic Games, or Rockstar Games Launcher).
- Direct protocol launching for Steam and Epic Games Store, replacing desktop shortcut scanning.
- Automated release builds via GitHub Actions.

### Fixed

- Added clear error message when Rockstar Games Launcher is selected but not installed.

## [1.0.6] - 2024-07-02

### Added

- "Start GTA 5" button in the Inject tab to launch the game directly from YMU.
- Combined help dialog explaining game launching and DLL injection workflows.

### Changed

- Reorganized Settings and Inject tabs into structured card frames with interactive hover highlights.
- Automatically migrated downloaded DLL storage to `ymu/dll/`.

## [1.0.5] - 2024-06-21

### Added

- "Enable External Debug Console" toggle in Settings to control YimMenu's console window.
- "Open in Browser" button in the Changelog window to open release notes on GitHub.

### Changed

- Polished toggle switch colors and hover effects.

## [1.0.4] - 2024-06-16

### Added

- Theme selection supporting Dark and Light modes.
- "Enable Auto Reload for Lua-Scripts" toggle in Settings.
- "Discover Luas" shortcut button to find community scripts.
- Interactive hover animations and color transitions on UI controls.

## [1.0.3] - 2024-06-11

### Added

- Dedicated Settings tab with built-in updater.
- "Open YimMenu Folder" shortcut button in Settings.

### Changed

- Centered all popup windows on screen with automatic focus.
- Improved button states and visual feedback during injection.

## [1.0.2] - 2024-06-09

### Added

- In-app YimMenu changelog viewer.
- Official application icon (`ymu.ico`) and startup splash screen.

### Changed

- Consolidated separate "Download" and "Update" tabs into a unified tab.
- Replaced manual SHA-256 tab with automatic background integrity verification.

### Fixed

- Fixed an issue where background processes occasionally remained open after exiting YMU.

## [1.0.1] - 2024-06-02

### Added

- Dedicated "Inject" tab to inject `YimMenu.dll` directly into a running GTA V process.
- Visual injection progress feedback and step-by-step injection guide dialog.

## [1.0.0] - 2024-05-31

### Added

- Initial release of YimMenuUpdater (YMU).
- Automated download of nightly `YimMenu.dll` releases from GitHub.
- SHA-256 checksum verification to ensure downloaded file integrity.
- Real-time download progress bar and status indicators.
- Clean, dark-themed desktop interface.

[Unreleased]: https://github.com/NiiV3AU/YMU/compare/v1.1.11...HEAD
[1.2.0]: https://github.com/NiiV3AU/YMU/compare/v1.1.11...v1.2.0
[1.1.11]: https://github.com/NiiV3AU/YMU/compare/v1.1.10...v1.1.11
[1.1.10]: https://github.com/NiiV3AU/YMU/compare/v1.1.9...v1.1.10
[1.1.9]: https://github.com/NiiV3AU/YMU/compare/v1.1.8...v1.1.9
[1.1.8]: https://github.com/NiiV3AU/YMU/compare/v1.1.7...v1.1.8
[1.1.7]: https://github.com/NiiV3AU/YMU/compare/v1.1.6...v1.1.7
[1.1.6]: https://github.com/NiiV3AU/YMU/compare/v1.1.5...v1.1.6
[1.1.5]: https://github.com/NiiV3AU/YMU/compare/v1.1.4...v1.1.5
[1.1.4]: https://github.com/NiiV3AU/YMU/compare/v1.1.3...v1.1.4
[1.1.3]: https://github.com/NiiV3AU/YMU/compare/v1.1.2...v1.1.3
[1.1.2]: https://github.com/NiiV3AU/YMU/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/NiiV3AU/YMU/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/NiiV3AU/YMU/compare/v1.0.9...v1.1.0
[1.0.9]: https://github.com/NiiV3AU/YMU/compare/v1.0.8...v1.0.9
[1.0.8]: https://github.com/NiiV3AU/YMU/compare/v1.0.7...v1.0.8
[1.0.7]: https://github.com/NiiV3AU/YMU/compare/v1.0.6...v1.0.7
[1.0.6]: https://github.com/NiiV3AU/YMU/compare/v1.0.5...v1.0.6
[1.0.5]: https://github.com/NiiV3AU/YMU/compare/v1.0.4...v1.0.5
[1.0.4]: https://github.com/NiiV3AU/YMU/compare/v1.0.3...v1.0.4
[1.0.3]: https://github.com/NiiV3AU/YMU/compare/v1.0.2...v1.0.3
[1.0.2]: https://github.com/NiiV3AU/YMU/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/NiiV3AU/YMU/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/NiiV3AU/YMU/releases/tag/v1.0.0
