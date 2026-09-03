# download_page.py - Handles downloading and updating YimMenu DLLs.
import logging
import os
import time
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from core import release_service
from core.config import get_config
from core.menu_modes import MenuMode
from core.paths import YMU_DLL_DIR, resource_path
from ui.utils import play_success_sound
from ui.widgets.buttons import AnimatedButton, StatefulButton
from ui.widgets.dialogs import InfoDialog

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
    from ui.main_window import MainWindow
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class DownloadPage(QWidget):
    STATUS_UPTODATE = "STATUS_UPTODATE"
    STATUS_DOWNLOAD = "STATUS_DOWNLOAD"
    STATUS_UPDATE = "STATUS_UPDATE"

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

        # Set only on the GUI thread, from the last check whose edition still
        # matched. Read by start_download to know what to download.
        self.latest_release_data = None
        self._release_cache = {}
        self.CACHE_DURATION_SECONDS = 300

        self.is_download_ready = False

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
                "Download.Tooltip.Help", "Show help for DLL and FSL installation"
            )
        )
        info_button.setIconSize(QSize(20, 20))

        self.channel_label = QLabel(self.get_mode().display_name)
        self.channel_label.setObjectName("SettingsTitle")
        self.channel_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.channel_label.setToolTip(
            self.loc_manager.tr(
                "Download.Tooltip.ActiveChannel",
                "Active edition — change it with the Legacy/Enhanced switch in the sidebar",
            )
        )
        self.status_label = QLabel(
            self.loc_manager.tr(
                "Download.Status.Initial", "Select a channel to check for updates."
            )
        )
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.download_button = AnimatedButton(
            self.loc_manager.tr("Download.Btn.Check", "Check for Updates"),
            theme_manager=self.theme_manager,
        )
        self.download_button.setMinimumWidth(140)
        self.download_button.setFixedHeight(40)
        self.download_button.setEnabled(True)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(info_button)

        card_frame = QFrame()
        card_frame.setObjectName("CardFrame")
        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(15)
        card_layout.addWidget(self.channel_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(
            self.download_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(card_frame)
        centering_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(header_layout)
        main_layout.addStretch()
        main_layout.addLayout(centering_layout)
        main_layout.addStretch()

        info_button.clicked.connect(self.show_download_info_dialog)
        self.download_button.clicked.connect(self._on_download_button_clicked)

        self.trigger_update_check()

    def on_mode_changed(self, mode: MenuMode):
        """Slot: the sidebar switch changed the active edition."""
        self.channel_label.setText(mode.display_name)
        self.trigger_update_check()

    def _on_download_button_clicked(self):
        """This handler decides what happens when you click."""
        if self.is_download_ready:
            self.start_download()
        else:
            self.trigger_update_check()

    def trigger_update_check(self):
        """Starts the update check for the currently selected channel."""
        self.is_download_ready = False

        self.status_label.setText(
            self.loc_manager.tr("Download.Status.Checking", "Checking for updates...")
        )
        self.download_button.setEnabled(False)
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Checking", "Checking...")
        )

        # Capture everything mode-dependent on the GUI thread and pass it to
        # the worker as arguments. The worker reads no shared/mode state, so a
        # mode switch mid-check cannot mix editions; the result carries its
        # own mode key so the callback can discard it if it is stale.
        mode = self.get_mode()
        provider = release_service.GitHubAPIProvider(repository=mode.repo)
        local_dll_path = os.path.join(YMU_DLL_DIR, mode.dll_name)

        self.worker_manager.run_task(
            self._update_check_logic,
            provider,
            mode.repo,
            local_dll_path,
            mode.key,
            on_finished=self._handle_update_check_result,
            on_error=self._handle_worker_error,
        )

    def update_download_progress(self, percentage: int):
        self.download_button.set_progress(percentage / 100.0)

    def show_download_info_dialog(self):
        """Creates and displays the info dialog for the download page."""

        dll_info_default = (
            "1. Click on (Download)\n"
            "2. Wait for the download to finish\n"
            "3. The file is in the 'YMU/dll' folder\n\n"
            "If the file gets deleted, add an exception\n"
            "in your antivirus or disable it temporarily."
        )
        dll_info_text = self.loc_manager.tr("Download.Help.DllSteps", dll_info_default)

        fsl_info_default = (
            "1. Download FSL (Link provided in the Risks Page)\n"
            "2. Open your GTAV Directory\n"
            "3. Drop the WINMM.dll in the folder\n"
            "   (filename MUST be exactly 'WINMM.dll')\n"
            "4. Disable BattlEye in Rockstar's Game Launcher\n"
            "5. Done! ✅"
        )
        fsl_info_text = self.loc_manager.tr("Download.Help.FslSteps", fsl_info_default)

        content = {"DLL": dll_info_text, "FSL": fsl_info_text}

        dialog = InfoDialog(
            title=self.loc_manager.tr("Download.Help.Title", "DLL & FSL Info"),
            content=content,
            theme_manager=self.theme_manager,
            parent=self,
        )
        dialog.exec()

    def _update_check_logic(
        self,
        provider,
        repo_path: str,
        local_dll_path: str,
        mode_key: str,
        progress_signal=None,
    ):
        """
        Fetches the latest release data. Fully self-contained (everything is
        passed in), so it never reads shared/mode state on the worker thread.
        Returns (mode_key, STATUS_CONSTANT, release_data) so the GUI callback
        can discard a result whose edition is no longer selected.
        """
        current_time = time.time()

        if repo_path in self._release_cache:
            cached_data, timestamp = self._release_cache[repo_path]
            if (current_time - timestamp) < self.CACHE_DURATION_SECONDS:
                logger.info(f"Using cached release data for {repo_path}.")
                status = self._compare_checksums(cached_data, local_dll_path)
                return (mode_key, status, cached_data)

        logger.info(f"Fetching fresh release data for {repo_path}.")
        release_data = provider.get_latest_release()

        if not release_data:
            raise RuntimeError("Failed to fetch release data from GitHub.")

        self._release_cache[repo_path] = (release_data, current_time)
        status = self._compare_checksums(release_data, local_dll_path)
        return (mode_key, status, release_data)

    def _compare_checksums(self, release_data, local_dll_path: str):
        """Pure helper: map the release checksum vs the local DLL to a status.

        No local DLL means "download". "Up-to-date" is reported only when the
        local file matches a real remote checksum. Anything else (a mismatch,
        or a release whose notes carry no SHA256) counts as "update available",
        which avoids a ``None == None`` false "up-to-date" that would strand a
        fresh user with the download button disabled."""
        local_checksum = release_service.get_local_sha256(local_dll_path)

        if local_checksum is None:
            return self.STATUS_DOWNLOAD
        if release_data.checksum and local_checksum == release_data.checksum:
            return self.STATUS_UPTODATE
        if not release_data.checksum:
            logger.warning(
                "Remote release has no SHA256; cannot confirm the local DLL is "
                "current, so offering an update instead of 'up-to-date'."
            )
        return self.STATUS_UPDATE

    def _handle_update_check_result(self, result):
        mode_key, status, release_data = result
        # Discard a check whose edition is no longer selected (the user toggled
        # the sidebar switch while it was in flight); a fresh check for the
        # current edition is already running.
        if mode_key != self.get_mode().key:
            logger.info(f"Discarding stale update-check result for '{mode_key}'.")
            return
        self.latest_release_data = release_data
        if status == self.STATUS_UPTODATE:
            self.is_download_ready = False
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.UpToDate", "YimMenu is up-to-date."
                )
            )
            self.download_button.setText(
                self.loc_manager.tr("Download.Btn.UpToDate", "Up-to-date")
            )
            self.download_button.setEnabled(False)

        elif status in [self.STATUS_DOWNLOAD, self.STATUS_UPDATE]:
            self.is_download_ready = True
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.NewVersion", "A new version is available!"
                )
            )

            btn_key = (
                "Download.Btn.Update"
                if status == self.STATUS_UPDATE
                else "Download.Btn.Download"
            )
            self.download_button.setText(self.loc_manager.tr(btn_key))
            self.download_button.setEnabled(True)

            title_fmt = self.loc_manager.tr("Download.Notify.UpdateTitle", "{0} Update")
            cast("MainWindow", self.window()).notification_manager.show(
                title_fmt.format(self.get_mode().display_name),
                self.loc_manager.tr(
                    "Download.Notify.NewVersion", "A new version is ready."
                ),
                icon_type="info",
            )

    def _handle_worker_error(self, error: Exception):
        """Callback for any error originating from the worker."""
        self.is_download_ready = False
        self.status_label.setText(
            self.loc_manager.tr(
                "Download.Status.Error", "An error occurred. Please try again."
            )
        )
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Retry", "Retry Check")
        )
        self.download_button.setEnabled(True)

        if isinstance(error, release_service.RateLimitException) and error.wait_minutes:
            err_msg = self.loc_manager.tr(
                "Download.Error.RateLimited",
                "GitHub API rate limit reached. Please try again in {0} minutes.",
            ).format(error.wait_minutes)
        else:
            err_msg = f"{self.loc_manager.tr('Download.Notify.CheckFailed', 'Failed to check for updates')}: {error}"

        cast("MainWindow", self.window()).notification_manager.show(
            self.loc_manager.tr("Common.Error", "Error"),
            err_msg,
            icon_type="error",
        )

    def start_download(self):
        """Starts the download process."""
        if not self.latest_release_data:
            self._handle_worker_error(
                RuntimeError("No release information to start download.")
            )
            return

        release_data = self.latest_release_data

        if not release_data.checksum:
            tr = self.loc_manager.tr
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(
                tr("Download.Dialog.UnverifiedTitle", "Unverified DLL Download")
            )
            box.setText(
                tr(
                    "Download.Dialog.UnverifiedPrompt",
                    "No SHA256 checksum was provided with this release.\n\n"
                    "YMU cannot verify the integrity or authenticity of the file.\n\n"
                    "Do you want to download it anyway?",
                )
            )
            proceed = box.addButton(
                tr("Download.Dialog.DownloadAnyway", "Download anyway"),
                QMessageBox.ButtonRole.AcceptRole,
            )
            cancel = box.addButton(
                tr("Common.Cancel", "Cancel"), QMessageBox.ButtonRole.RejectRole
            )
            box.setDefaultButton(cancel)
            box.exec()
            if box.clickedButton() is not proceed:
                return

        self.status_label.setText(
            f"{self.loc_manager.tr('Download.Status.Downloading', 'Downloading')} {release_data.asset_name}..."
        )
        self.download_button.setEnabled(False)
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.Downloading", "Downloading...")
        )
        self.download_button.stop_animation()
        QApplication.processEvents()

        # Capture the release and current mode on the GUI thread so a later mode
        # switch cannot swap it out from under the running download.
        mode_key = self.get_mode().key
        self.worker_manager.run_task(
            self._download_logic,
            release_data,
            mode_key,
            on_finished=self._handle_download_result,
            on_error=self._handle_worker_error,
            on_progress=self.update_download_progress,
        )

    def _download_logic(self, release_data, mode_key: str, progress_signal=None):
        """Runs in the background and executes the download."""

        def progress_callback(percentage):
            if progress_signal:
                progress_signal.emit(percentage)

        success, is_verified = release_service.download_and_verify_release(
            release_data, progress_callback
        )
        return (mode_key, success, is_verified)

    def _handle_download_result(self, result: tuple[str, bool, bool]):
        mode_key, success, is_verified = result
        if mode_key != self.get_mode().key:
            logger.info(f"Discarding stale download result for '{mode_key}'.")
            return

        if success:
            if get_config().get("inject.sound_feedback", True):
                play_success_sound()
            self.download_button.set_progress(1.0)
            status_text = (
                self.loc_manager.tr(
                    "Download.Status.Success", "Download successful and verified!"
                )
                if is_verified
                else self.loc_manager.tr(
                    "Download.Status.SuccessUnverified",
                    "Download successful (unverified)!",
                )
            )
            self.status_label.setText(status_text)

            msg_text = (
                self.loc_manager.tr(
                    "Download.Notify.SuccessMsg",
                    "DLL successfully downloaded and verified!",
                )
                if is_verified
                else self.loc_manager.tr(
                    "Download.Notify.SuccessMsgUnverified",
                    "DLL downloaded successfully, but could not be verified (no remote checksum).",
                )
            )
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr(
                    "Download.Notify.SuccessTitle", "Download Complete"
                ),
                msg_text,
                icon_type="success",
            )

            QTimer.singleShot(400, self._set_to_uptodate_state)
        else:
            self.download_button.reset_progress()
            cast("MainWindow", self.window()).notification_manager.show(
                self.loc_manager.tr("Download.Notify.FailedTitle", "Download Failed"),
                self.loc_manager.tr(
                    "Download.Notify.FailedMsg",
                    "Verification failed. Please check the logs.",
                ),
                icon_type="error",
            )
            self.status_label.setText(
                self.loc_manager.tr(
                    "Download.Status.Failed", "Download failed. Check logs."
                )
            )
            self.download_button.setEnabled(True)
            self.download_button.setText(
                self.loc_manager.tr("Download.Btn.Update", "Update")
            )
            self.is_download_ready = True

    def _set_to_uptodate_state(self):
        """Helper method to set the final UI state."""
        self.download_button.reset_progress()
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.UpToDate", "Up-to-date")
        )
        self.download_button.setEnabled(False)
        self.is_download_ready = False
