# inject_page.py - Handles launcher selection, game startup, and DLL injection.
import logging
import os
import time
import webbrowser
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core import menu_modes, process_manager
from core.config import get_config
from core.menu_modes import MenuMode
from core.paths import YMU_DLL_DIR, resource_path
from ui.utils import restart_as_admin
from ui.widgets.buttons import AnimatedButton, StatefulButton
from ui.widgets.dialogs import InfoDialog

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
    from ui.main_window import MainWindow
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class InjectPage(QWidget):
    STATE_IDLE = "IDLE"
    STATE_LAUNCHING = "LAUNCHING"
    STATE_APP_RUNNING = "APP_RUNNING"
    STATE_INJECTING = "INJECTING"
    STATE_INJECTED = "INJECTED"

    # If GTA V never appears within this many seconds of launching (the user
    # closed it, or it crashed during load), stop waiting and re-enable the
    # Start button instead of spinning forever.
    LAUNCH_TIMEOUT_S = 60

    # Stable launcher keys, stored as combo item-data and in the config, so the
    # logic and the remembered selection never depend on the (translatable)
    # display text.
    LAUNCHER_STEAM = "steam"
    LAUNCHER_EPIC = "epic"
    LAUNCHER_ROCKSTAR = "rockstar"
    LAUNCHER_CUSTOM = "custom"

    def __init__(
        self,
        theme_manager: "ThemeManager",
        worker_manager: "WorkerManager",
        loc_manager: "LocalizationManager",
        get_mode,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self.get_mode = get_mode

        self.gta_pid = None
        self._state = self.STATE_IDLE
        self._launch_started_at = 0.0
        self.dll_to_inject = None

        info_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "help-circle.svg")),
            color_normal=("#8B8B8B", "#777777"),
            color_hover=("#E0E0E0", "#121212"),
        )
        info_button.setObjectName("InfoButton")

        info_button.setToolTip(
            self.loc_manager.tr(
                "Inject.Tooltip.Help", "Show help for the injection process"
            )
        )
        info_button.setIconSize(QSize(20, 20))

        self.launcher_select = QComboBox()
        self.launcher_select.setFixedWidth(175)
        self.launcher_select.setToolTip(
            self.loc_manager.tr(
                "Inject.Tooltip.Launcher", "Select the launcher you use to start GTA V"
            )
        )
        self.launcher_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self._rebuild_launcher_options()

        self.dll_select = QComboBox()
        self.dll_select.setToolTip(
            self.loc_manager.tr("Inject.Tooltip.Dll", "Select the DLL to inject")
        )
        self.dll_select.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dll_select.setVisible(False)

        self.start_gta_button = AnimatedButton(
            self.loc_manager.tr("Inject.Btn.StartGta", "Start GTA 5"),
            theme_manager=self.theme_manager,
        )
        self.start_gta_button.setEnabled(False)

        self.inject_button = AnimatedButton(
            self.loc_manager.tr("Inject.Btn.InjectBase", "Inject YimMenu"),
            theme_manager=self.theme_manager,
        )
        self.inject_button.setEnabled(False)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(info_button)

        controls_frame = QFrame()
        controls_frame.setObjectName("CardFrame")
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setSpacing(15)
        controls_layout.addWidget(
            self.launcher_select, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.dll_select, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.start_gta_button, alignment=Qt.AlignmentFlag.AlignCenter
        )
        controls_layout.addWidget(
            self.inject_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        centering_controls_layout = QHBoxLayout()
        centering_controls_layout.addStretch()
        centering_controls_layout.addWidget(controls_frame)
        centering_controls_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(header_layout)
        main_layout.addStretch()
        main_layout.addLayout(centering_controls_layout)
        main_layout.addStretch()

        info_button.clicked.connect(self.show_inject_info_dialog)
        self.start_gta_button.clicked.connect(self.handle_start_gta_click)
        self.inject_button.clicked.connect(self.handle_inject_click)
        self.launcher_select.currentIndexChanged.connect(
            self._on_launcher_selection_changed
        )
        self.dll_select.currentIndexChanged.connect(self._on_dll_selection_changed)

        self.process_checker_timer = QTimer(self)
        self.process_checker_timer.setInterval(3000)
        self.process_checker_timer.timeout.connect(self._run_process_check)

    def showEvent(self, event):
        """Called every time the page becomes visible."""
        super().showEvent(event)
        # Rebuild here so a custom path added on the Settings page shows up as a
        # launcher option, and a cleared one disappears.
        self._rebuild_launcher_options()
        self._update_dll_selector()
        self.process_checker_timer.start()
        logger.debug("InjectPage shown, started process checker timer.")

    def _rebuild_launcher_options(self):
        """(Re)builds the launcher dropdown. 'Custom Path' is offered only when a
        custom GTA V install directory is configured. The last saved selection is
        restored when still valid; an invalid one (e.g. 'custom' after the path
        was cleared) is discarded and the placeholder is shown instead."""
        saved = get_config().get("inject.launcher")
        combo = self.launcher_select

        combo.blockSignals(True)
        combo.clear()
        combo.addItem(
            self.loc_manager.tr("Inject.Launcher.Select", "Select Launcher"), ""
        )
        combo.addItem("Steam", self.LAUNCHER_STEAM)
        combo.addItem("Epic Games", self.LAUNCHER_EPIC)
        combo.addItem("Rockstar Games", self.LAUNCHER_ROCKSTAR)
        if get_config().get("paths.gta_dir"):
            combo.addItem(
                self.loc_manager.tr("Inject.Launcher.CustomPath", "Custom Path"),
                self.LAUNCHER_CUSTOM,
            )

        idx = combo.findData(saved) if saved else -1
        if saved and idx <= 0:
            # The saved launcher is no longer available — discard it for good.
            get_config().set("inject.launcher", None)
        combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)

    def hideEvent(self, event):
        """Called every time the page is hidden."""
        super().hideEvent(event)
        self.process_checker_timer.stop()
        logger.debug("InjectPage hidden, stopped process checker timer.")

    def on_mode_changed(self, mode: MenuMode):
        """Slot: the sidebar switch changed the active edition.
        The old PID belongs to the other edition's executable, so reset."""
        self.gta_pid = None
        self._set_state(self.STATE_IDLE)
        self._update_dll_selector()

    def _set_state(self, new_state):
        """The only function that should ever change the state."""
        logger.debug(f"State changed: {self._state} -> {new_state}")
        self._state = new_state
        self._update_ui_for_state()

    def _update_ui_for_state(self):
        """Updates the entire UI based on the current state."""
        is_launcher_selected = self.launcher_select.currentIndex() > 0
        has_dll = self.dll_to_inject is not None

        if self._state == self.STATE_IDLE:
            self.start_gta_button.setEnabled(is_launcher_selected)
            self.inject_button.setEnabled(False)
            self.start_gta_button.stop_animation()

        elif self._state == self.STATE_LAUNCHING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.start_gta_button.start_animation()

        elif self._state == self.STATE_APP_RUNNING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(has_dll)
            self.start_gta_button.stop_animation()

        elif self._state == self.STATE_INJECTING:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.inject_button.start_animation(duration=500)

        elif self._state == self.STATE_INJECTED:
            self.start_gta_button.setEnabled(False)
            self.inject_button.setEnabled(False)
            self.inject_button.stop_animation()

    def _update_dll_selector(self):
        """Builds the DLL choice for the active edition. The Legacy/Enhanced
        DLL follows the global sidebar toggle, so the only real choice is
        whether to use it or a user-configured custom DLL. The selector is
        therefore only shown when a custom DLL is present alongside the
        edition's DLL. dll_to_inject is an absolute path."""
        dll_dir = YMU_DLL_DIR
        os.makedirs(dll_dir, exist_ok=True)
        mode = self.get_mode()

        self._dll_paths: dict[str, str] = {}
        self._edition_dll_name: str | None = None
        self._custom_dll_name: str | None = None

        # The DLL that matches the currently selected edition.
        mode_dll_path = os.path.join(dll_dir, mode.dll_name)
        if os.path.isfile(mode_dll_path):
            self._edition_dll_name = mode.dll_name.removesuffix(".dll")
            self._dll_paths[self._edition_dll_name] = mode_dll_path

        custom_dll = get_config().get("paths.custom_dll")
        if custom_dll:
            if os.path.isfile(custom_dll):
                label = "{} ({})".format(
                    os.path.basename(custom_dll).removesuffix(".dll"),
                    self.loc_manager.tr("Inject.Label.Custom", "custom"),
                )
                self._custom_dll_name = label
                self._dll_paths[label] = custom_dll
            elif not getattr(self, "_warned_missing_custom_dll", False):
                self._warned_missing_custom_dll = True
                cast("MainWindow", self.window()).notification_manager.show(
                    self.loc_manager.tr("Common.Info", "Information"),
                    self.loc_manager.tr(
                        "Inject.Notify.CustomDllMissing",
                        "The configured custom DLL no longer exists:\n{0}",
                    ).format(custom_dll),
                    icon_type="info",
                )

        names = list(self._dll_paths.keys())
        self.dll_select.blockSignals(True)
        self.dll_select.clear()

        if len(names) == 0:
            self.dll_select.setVisible(False)
            self.dll_to_inject = None
            self.inject_button.setText(
                self.loc_manager.tr("Inject.Btn.NoDll", "No DLL found")
            )
            self.inject_button.setToolTip(
                self.loc_manager.tr(
                    "Inject.Tooltip.NoDll",
                    "Download the {0} DLL on the Download page first.",
                ).format(mode.display_name)
            )
            self.inject_button.setEnabled(False)

        elif len(names) == 1:
            self.dll_select.setVisible(False)
            self.dll_to_inject = self._dll_paths[names[0]]
            self.inject_button.setToolTip("")
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(names[0]))

        else:
            self.dll_select.addItems(names)
            self.dll_select.setVisible(True)
            self.inject_button.setToolTip("")
            # Restore the saved choice (edition vs custom) when it is still
            # available; otherwise fall back to the edition DLL.
            saved_choice = get_config().get("inject.dll_choice")
            if saved_choice == "custom" and self._custom_dll_name in self._dll_paths:
                self.dll_select.setCurrentText(self._custom_dll_name)
            elif self._edition_dll_name in self._dll_paths:
                self.dll_select.setCurrentText(self._edition_dll_name)
            current_name = self.dll_select.currentText()
            self.dll_to_inject = self._dll_paths[current_name]
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(current_name))

        self.dll_select.blockSignals(False)
        self._update_ui_for_state()

    def _on_dll_selection_changed(self, index):
        """Updates the DLL to inject and remembers the choice (edition/custom)."""
        name = self.dll_select.currentText()
        if index > -1 and name in getattr(self, "_dll_paths", {}):
            fmt = self.loc_manager.tr("Inject.Btn.InjectFile", "Inject {0}")
            self.inject_button.setText(fmt.format(name))
            self.dll_to_inject = self._dll_paths[name]
            choice = "custom" if name == self._custom_dll_name else "edition"
            get_config().set("inject.dll_choice", choice)
        self._update_ui_for_state()

    def _on_launcher_selection_changed(self):
        """Persists the choice and enables/disables the start button."""
        key = self.launcher_select.currentData()
        get_config().set("inject.launcher", key if key else None)
        self._update_ui_for_state()

    def show_inject_info_dialog(self):
        start_gta_default = (
            "1. Select your launcher\n2. Press 'Start GTA 5'\n3. Read the next step ↗"
        )
        start_gta_text = self.loc_manager.tr(
            "Inject.Help.StartGtaSteps", start_gta_default
        )

        inject_default = (
            "1. Start GTA 5 (↖ Previous Step)\n"
            "2. Wait for the game's start screen/menu\n"
            "3. Click on 'Inject YimMenu'\n"
            "4. Wait for YimMenu to finish loading\n"
            "5. Done! ✅"
        )
        inject_text = self.loc_manager.tr("Inject.Help.InjectSteps", inject_default)

        content = {
            self.loc_manager.tr("Inject.Btn.StartGta", "Start GTA 5"): start_gta_text,
            self.loc_manager.tr("Inject.Help.TabInject", "Inject DLL"): inject_text,
        }

        dialog = InfoDialog(
            title=self.loc_manager.tr("Inject.Help.Title", "Injection Info"),
            content=content,
            theme_manager=self.theme_manager,
            parent=self,
        )
        dialog.exec()

    def handle_start_gta_click(self):
        if self._state != self.STATE_IDLE:
            return
        if process_manager.find_gta_pid(self.get_mode().target_executables) is not None:
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Info", "Information"),
                self.loc_manager.tr(
                    "Inject.Notify.AlreadyRunning", "GTA 5 is already running!"
                ),
                icon_type="info",
            )
            return
        if self.launcher_select.currentIndex() == 0:
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Error", "Error"),
                self.loc_manager.tr(
                    "Inject.Notify.SelectLauncher", "Please select a launcher first."
                ),
                icon_type="error",
            )
            return

        self._launch_started_at = time.monotonic()
        self._set_state(self.STATE_LAUNCHING)
        # Capture everything the worker needs on the GUI thread; it must not read
        # widgets or the live mode.
        launcher = self.launcher_select.currentData()
        mode = self.get_mode()
        custom_dir = get_config().get("paths.gta_dir")
        self.worker_manager.run_task(
            self._launch_game_logic,
            launcher,
            mode,
            custom_dir,
            on_finished=self.on_launch_attempt_finished,
            on_error=self.on_task_error,
        )

    def _start_game_from_dir(self, path: str, mode: MenuMode) -> str:
        """Finds the edition's launch executable inside `path` and starts it.
        PlayGTAV.exe is the normal launcher shim; the direct edition executable
        is the fallback for exotic installs."""
        executable_path = next(
            (
                os.path.join(path, exe)
                for exe in mode.launch_executables
                if os.path.exists(os.path.join(path, exe))
            ),
            None,
        )
        if not executable_path:
            msg = self.loc_manager.tr(
                "Inject.Error.NoExeFound", "Executable not found at '{0}'"
            ).format(path)
            logger.error(msg)
            raise FileNotFoundError(msg)
        try:
            os.startfile(executable_path)
            return "Success"
        except OSError as e:
            logger.exception(f"Failed to start {executable_path}")
            msg = self.loc_manager.tr(
                "Inject.Error.LaunchFailed",
                "Error launching game. See logs for details.",
            )
            raise RuntimeError(msg) from e

    def _launch_game_logic(
        self, launcher: str, mode: MenuMode, custom_dir, progress_signal=None
    ):
        """Contains the actual logic for launching the game for a given
        edition. `launcher` is a stable key (see LAUNCHER_* constants)."""
        logger.info(
            f"Attempting to launch {mode.display_name} via '{launcher}' launcher."
        )

        if launcher == self.LAUNCHER_STEAM:
            uri = mode.steam_uri
        elif launcher == self.LAUNCHER_EPIC:
            uri = menu_modes.EPIC_LAUNCH_URI
        else:
            uri = None

        if uri:
            try:
                webbrowser.open(uri)
                logger.info(f"Successfully sent launch command to '{launcher}'.")
                return f"Launch command sent to {launcher}."
            except Exception as e:
                logger.exception(f"Failed to open URI for {launcher}")
                raise RuntimeError(f"Could not send command to {launcher}.") from e

        elif launcher == self.LAUNCHER_ROCKSTAR:
            path = menu_modes.get_install_dir(mode)
            if not path:
                msg = self.loc_manager.tr(
                    "Inject.Error.NoRockstarPath",
                    "Could not find Rockstar Games installation path.",
                )
                logger.error(msg)
                raise FileNotFoundError(msg)
            return self._start_game_from_dir(path, mode)

        elif launcher == self.LAUNCHER_CUSTOM:
            if not custom_dir or not os.path.isdir(custom_dir):
                msg = self.loc_manager.tr(
                    "Inject.Error.CustomPathInvalid",
                    "The custom GTA V path is not set or no longer exists.\n"
                    "Set it again on the Settings page.",
                )
                logger.error(msg)
                raise FileNotFoundError(msg)
            return self._start_game_from_dir(custom_dir, mode)

        else:
            logger.error(
                f"Logic Error: Attempted to launch with unhandled launcher: {launcher}"
            )
            raise ValueError(f"Internal Error: Unhandled launcher {launcher}")

    def on_launch_attempt_finished(self, result: str):
        """Callback for when the game launch task finishes."""
        logger.info(f"Launch attempt finished with result: {result}")

    def _run_process_check(self):
        if self._state in [self.STATE_INJECTING]:
            return
        # run_exclusive prevents a timer tick from starting a second scan while
        # one is still running (e.g. a slow psutil sweep under load).
        self.worker_manager.run_exclusive(
            "gta_scan",
            process_manager.find_gta_pid,
            self.get_mode().target_executables,
            on_finished=self.update_inject_button_status,
        )

    def update_inject_button_status(self, pid: int | None):
        # A scan started just before an inject click can finish mid-injection;
        # applying its result would flip STATE_INJECTING back to APP_RUNNING.
        if self._state == self.STATE_INJECTING:
            return
        self.gta_pid = pid

        if self.gta_pid is not None:
            if self._state != self.STATE_INJECTED:
                self._set_state(self.STATE_APP_RUNNING)
        elif self._state == self.STATE_LAUNCHING:
            # Keep waiting through a normal (possibly slow) launch, but give up
            # if the game never appears — otherwise the Start button spins
            # forever when GTA is closed manually or crashes during load.
            if time.monotonic() - self._launch_started_at > self.LAUNCH_TIMEOUT_S:
                logger.info(
                    f"Launch timed out after {self.LAUNCH_TIMEOUT_S}s — GTA V did "
                    "not appear. Re-enabling the Start button."
                )
                self._set_state(self.STATE_IDLE)
                cast("MainWindow", self.window()).notification_manager.show(
                    self.loc_manager.tr("Common.Info", "Information"),
                    self.loc_manager.tr(
                        "Inject.Notify.LaunchTimeout",
                        "GTA V didn't start (or was closed before it loaded).\n"
                        "You can try launching again.",
                    ),
                    icon_type="info",
                )
        else:
            self._set_state(self.STATE_IDLE)

    def handle_inject_click(self):
        if self._state != self.STATE_APP_RUNNING:
            return

        # YMU informs, it does not block: if BattlEye is running, warn clearly
        # about the ban risk but let the user decide to inject anyway.
        if (
            process_manager.is_battleye_running()
            and not self._confirm_battleye_override()
        ):
            return

        self._set_state(self.STATE_INJECTING)
        # Capture PID and DLL on the GUI thread; the worker must not read
        # mutable page state. run_exclusive guards against a double injection.
        self.worker_manager.run_exclusive(
            "inject",
            self._inject_logic,
            self.gta_pid,
            self.dll_to_inject,
            on_finished=self.on_injection_complete,
            on_error=self.on_task_error,
        )

    def _confirm_battleye_override(self) -> bool:
        """BattlEye is active. Warn about the ban risk and let the user choose —
        YMU never blocks a deliberate decision. Returns True to inject anyway.

        Offers a third 'How to disable' choice that opens the Risks page and
        does not inject. The safe option (Cancel) is the default.
        """
        tr = self.loc_manager.tr
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("Inject.BattlEye.Title", "BattlEye Is Running"))
        box.setText(
            tr(
                "Inject.BattlEye.Warn",
                "BattlEye is active. Injecting while it runs can get your "
                "account banned and will often fail outright.\n\n"
                "This is entirely your decision and at your own risk — "
                "disabling BattlEye in your launcher first is strongly "
                "recommended.",
            )
        )
        proceed = box.addButton(
            tr("Inject.BattlEye.Proceed", "Inject anyway"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        learn = box.addButton(
            tr("Inject.BattlEye.Learn", "How to disable"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel = box.addButton(
            tr("Common.Cancel", "Cancel"), QMessageBox.ButtonRole.RejectRole
        )
        box.setDefaultButton(cancel)
        box.exec()

        clicked = box.clickedButton()
        if clicked is learn:
            cast("MainWindow", self.window()).show_risks_page()
            return False
        return clicked is proceed

    def _inject_logic(self, pid, dll_to_inject, progress_signal=None):
        """Contains the actual logic for injecting the DLL."""
        assert pid is not None

        if not dll_to_inject:
            msg = self.loc_manager.tr(
                "Inject.Error.NoDllSelected",
                "Error: No DLL selected or found for injection.",
            )
            raise ValueError(msg)

        if not process_manager.is_process_running(pid):
            msg = self.loc_manager.tr(
                "Inject.Error.ProcessLost",
                "GTA 5 process disappeared before injection.",
            )
            raise RuntimeError(msg)

        success = process_manager.inject_dll(pid, dll_to_inject)

        if success:
            return "Success"
        else:
            msg = self.loc_manager.tr(
                "Inject.Error.InjectionFailed",
                "Injection failed. See logs for details.",
            )
            raise RuntimeError(msg)

    def on_injection_complete(self, result: str):
        """Callback for when the injection task finishes."""
        self._set_state(self.STATE_INJECTED)
        logger.info(f"Injection finished with result: {result}")

        cast("MainWindow", self.window()).notification_manager.show(
            self.loc_manager.tr("Inject.Notify.SuccessTitle", "Injection Successful"),
            self.loc_manager.tr(
                "Inject.Notify.SuccessMsg", "Successfully injected DLL!"
            ),
            icon_type="success",
        )

    def on_task_error(self, error: Exception):
        logger.error(f"A task failed in the background: {error}")
        if self.gta_pid:
            self._set_state(self.STATE_APP_RUNNING)
        else:
            self._set_state(self.STATE_IDLE)
        if isinstance(error, process_manager.InjectionError):
            title, message, duration = self._injection_error_message(error)
            win = cast("MainWindow", self.window())
            action_text = None
            action_callback = None
            if error.reason in ("dll_missing", "module_not_found", "not_a_dll"):
                # A fresh download fixes a missing/incomplete/wrong DLL.
                action_text = self.loc_manager.tr(
                    "Inject.Error.RedownloadAction", "Re-download DLL"
                )
                action_callback = win.show_download_page
            win.notification_manager.show(
                title,
                message,
                icon_type="error",
                duration=duration,
                action_text=action_text,
                action_callback=action_callback,
            )
            return
        if isinstance(error, PermissionError) or "Access Denied" in str(error):
            if process_manager.is_admin():
                # Already elevated — admin rights are not the problem, so a
                # "Restart as Admin" loop (issue #17) would never resolve it.
                # The usual culprit is BattlEye or an edition mismatch.
                msg = self.loc_manager.tr(
                    "Inject.Error.AccessDeniedAdmin",
                    "Injection was denied even with Administrator rights.\n"
                    "This is usually caused by BattlEye or a wrong game edition.\n"
                    "Disable BattlEye in your launcher (see Risks page) and make\n"
                    "sure the Legacy/Enhanced switch matches your game.",
                )
                cast("MainWindow", self.window()).notification_manager.show(
                    self.loc_manager.tr("Common.Error", "Permission Error"),
                    msg,
                    icon_type="error",
                    duration=12000,
                )
                return
            msg = self.loc_manager.tr(
                "Inject.Error.AccessDenied",
                "Missing permissions to inject into GTA V.\nTry restarting YMU as Administrator.",
            )
            action_text = self.loc_manager.tr("Common.RestartAdmin", "Restart as Admin")
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Error", "Permission Error"),
                msg,
                icon_type="error",
                duration=10000,
                action_text=action_text,
                action_callback=restart_as_admin,
            )
        else:
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr("Common.Error", "An Error Occurred"),
                str(error),
                icon_type="error",
            )

    def _injection_error_message(
        self, error: "process_manager.InjectionError"
    ) -> tuple[str, str, int]:
        """Maps a classified injection failure to (title, message, duration_ms)."""
        tr = self.loc_manager.tr
        reason = getattr(error, "reason", "unknown")
        if reason == "module_not_found":
            return (
                tr("Inject.Error.ModuleNotFoundTitle", "Injection Failed"),
                tr(
                    "Inject.Error.ModuleNotFound",
                    "GTA V could not load the YimMenu DLL — it may be incomplete "
                    "or missing a dependency.\n"
                    "Re-download it on the Download page. If it keeps failing, "
                    "install the latest Microsoft Visual C++ Redistributable (x64).",
                ),
                12000,
            )
        if reason == "dll_missing":
            return (
                tr("Inject.Error.DllMissingTitle", "DLL Not Found"),
                tr(
                    "Inject.Error.DllMissing",
                    "The menu DLL wasn't found on disk.\n"
                    "Your antivirus may have quarantined it — YimMenu is often "
                    "flagged. Add an exclusion, then re-download it on the "
                    "Download page.",
                ),
                12000,
            )
        if reason == "not_a_dll":
            return (
                tr("Inject.Error.NotADllTitle", "Not a Valid DLL"),
                tr(
                    "Inject.Error.NotADll",
                    "The selected file isn't a valid Windows DLL.\n"
                    "Pick the correct YimMenu DLL, or use YMU's built-in "
                    "download to get the right one.",
                ),
                10000,
            )
        if reason == "bad_architecture":
            return (
                tr("Inject.Error.BadArchTitle", "Incompatible DLL"),
                tr(
                    "Inject.Error.BadArch",
                    "GTA V needs a 64-bit YimMenu DLL, but the selected DLL "
                    "isn't compatible.\n"
                    "Use the official DLL for your edition — both Legacy and "
                    "Enhanced are 64-bit.",
                ),
                10000,
            )
        if reason == "process_gone":
            return (
                tr("Inject.Error.ProcessGoneTitle", "Game Closed"),
                tr(
                    "Inject.Error.ProcessGone",
                    "GTA V closed before injection finished.\n"
                    "Start the game, wait for it to finish loading, then try again.",
                ),
                8000,
            )
        return (
            tr("Common.Error", "Injection Failed"),
            tr(
                "Inject.Error.Unknown",
                "Injection failed for an unexpected reason.\n"
                "See ymu.log for the full error.\n\nDetails: {0}",
            ).format(getattr(error, "detail", "") or str(error)),
            10000,
        )
