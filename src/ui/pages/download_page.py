# download_page.py - Handles downloading and updating YimMenu DLLs.
import logging
import os
import threading
import time
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
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
from ui.widgets.notifications import NotificationManager

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
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
        auto_check: bool = True,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self.get_mode = get_mode

        # latest_release_data is set only on the GUI thread from the last matching check.
        # _release_cache is thread-safe and protected by _cache_lock.
        self.latest_release_data = None
        self._release_cache = {}
        self._cache_lock = threading.Lock()
        self.CACHE_DURATION_SECONDS = 300
        self._check_seq: int = 0

        self.is_download_ready = False

        self.info_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "circle-help.svg")),
            color_normal=("#8B8B8B", "#777777"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.info_button.setObjectName("InfoButton")
        self.info_button.setToolTip(
            self.loc_manager.tr(
                "Download.Tooltip.Help", "Show help for DLL and FSL installation"
            )
        )
        self.info_button.setIconSize(QSize(20, 20))

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
        self.status_label.setWordWrap(True)
        self.status_label.setMaximumWidth(580)

        self.download_button = AnimatedButton(
            self.loc_manager.tr("Download.Btn.Check", "Check for Updates"),
            theme_manager=self.theme_manager,
        )
        self.download_button.setMinimumWidth(160)
        self.download_button.setMinimumHeight(44)
        self.download_button.setEnabled(True)

        header_layout = QHBoxLayout()
        header_layout.addStretch()
        header_layout.addWidget(self.info_button)

        self.card_frame = QFrame()
        self.card_frame.setObjectName("CardFrame")
        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setSpacing(16)
        card_layout.addWidget(self.channel_label)
        card_layout.addWidget(self.status_label)
        card_layout.addWidget(
            self.download_button, alignment=Qt.AlignmentFlag.AlignCenter
        )

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(self.card_frame)
        centering_layout.addStretch()

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.addLayout(header_layout)
        main_layout.addStretch()
        main_layout.addLayout(centering_layout)
        main_layout.addStretch()

        self.info_button.clicked.connect(self.show_download_info_dialog)
        self.download_button.clicked.connect(self._on_download_button_clicked)

        self.setTabOrder(self.download_button, self.info_button)

        if auto_check:
            self.trigger_update_check()

    def showEvent(self, event: QShowEvent) -> None:
        """Refresh update status if the local DLL was deleted or quarantined while away."""
        super().showEvent(event)
        mode = self.get_mode()
        dll_path = os.path.join(YMU_DLL_DIR, mode.dll_name)
        if not self.download_button.isEnabled() and not os.path.isfile(dll_path):
            logger.info(
                f"DownloadPage shown: local DLL '{dll_path}' missing; re-checking."
            )
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
        self._check_seq += 1
        seq = self._check_seq

        started = self.worker_manager.run_exclusive(
            f"update_check_{mode.key}",
            self._update_check_logic,
            provider,
            mode.repo,
            local_dll_path,
            mode.key,
            seq,
            on_finished=self._handle_update_check_result,
            on_error=self._handle_worker_error,
        )
        if not started:
            logger.info(f"Update check for '{mode.key}' already in progress; skipping duplicate.")

    def _notify(self, title: str, message: str, **kwargs):
        win = self.window()
        mgr = getattr(win, "notification_manager", None)
        if isinstance(mgr, NotificationManager):
            mgr.show(title, message, **kwargs)

    def update_download_progress(self, percentage: int):
        self.download_button.set_progress(percentage / 100.0)

    def show_download_info_dialog(self):
        """Creates and displays the info dialog for the download page."""

        dll_info_default = (
            "1. Click on [Download]\n"
            "2. Wait for the download to finish\n"
            "3. The file is in the '%LOCALAPPDATA%/YMU/dll' folder\n\n"
            "If the file gets deleted, add an exception\n"
            "in your antivirus or disable it temporarily."
        )
        dll_info_text = self.loc_manager.tr("Download.Help.DllSteps", dll_info_default)

        fsl_info_default = (
            "1. Download FSL (link provided in the Risks tab)\n"
            "2. Open your GTA V directory\n"
            "3. Drop the WINMM.dll in the folder\n"
            "   (filename MUST be exactly 'WINMM.dll')\n"
            "4. Disable BattlEye in the Rockstar Games Launcher\n"
            "5. Done!"
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
        seq: int,
    ):
        """Fetches the latest release data in a background worker task.
        Thread-safe under _cache_lock with synchronized in-memory caching and persistent ETag checks.
        Returns (mode_key, STATUS_CONSTANT, release_data, seq) so the GUI callback
        can discard a result whose edition or sequence is no longer selected.
        """
        try:
            current_time = time.time()
            cached_entry = None

            with self._cache_lock:
                if repo_path in self._release_cache:
                    cached_data, timestamp = self._release_cache[repo_path]
                    if (current_time - timestamp) < self.CACHE_DURATION_SECONDS:
                        cached_entry = cached_data

            if cached_entry is not None:
                logger.info(f"Using cached release data for {repo_path}.")
                status = self._compare_checksums(cached_entry, local_dll_path)
                return (mode_key, status, cached_entry, seq)

            logger.info(f"Fetching fresh release data for {repo_path}.")
            release_data = provider.get_latest_release()

            if not release_data:
                raise RuntimeError("Failed to fetch release data from GitHub.")

            with self._cache_lock:
                self._release_cache[repo_path] = (release_data, current_time)
            status = self._compare_checksums(release_data, local_dll_path)
            return (mode_key, status, release_data, seq)
        except Exception as e:
            setattr(e, "mode_key", mode_key)  # noqa: B010
            setattr(e, "seq", seq)  # noqa: B010
            raise

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
        mode_key, status, release_data, seq = result
        if seq != self._check_seq:
            logger.info(
                f"Discarding stale check result with sequence {seq}; current sequence is {self._check_seq}."
            )
            return
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
            self._notify(
                title_fmt.format(self.get_mode().display_name),
                self.loc_manager.tr(
                    "Download.Notify.NewVersion", "A new version is ready."
                ),
                icon_type="info",
            )

    def _handle_worker_error(self, error: Exception):
        """Callback for any error originating from the worker."""
        err_seq = getattr(error, "seq", None)
        if err_seq is not None and err_seq != self._check_seq:
            logger.info(
                f"Discarding stale download error with sequence {err_seq}; "
                f"current sequence is {self._check_seq}."
            )
            return
        err_mode_key = getattr(error, "mode_key", None)
        if err_mode_key and err_mode_key != self.get_mode().key:
            logger.info(
                f"Discarding stale download error for '{err_mode_key}'; "
                f"active mode is '{self.get_mode().key}'."
            )
            return

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
        elif isinstance(error, release_service.FileLockedException):
            err_msg = self.loc_manager.tr(
                "Download.Error.FileLocked",
                "YimMenu.dll is currently in use by GTA V or another process. Please close GTA V and try again.",
            )
        else:
            err_msg = f"{self.loc_manager.tr('Download.Notify.CheckFailed', 'Failed to check for updates')}: {error}"

        self._notify(
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
        self.download_button.update()

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

        try:
            success, is_verified = release_service.download_and_verify_release(
                release_data, progress_callback
            )
            return (mode_key, success, is_verified)
        except Exception as e:
            setattr(e, "mode_key", mode_key)  # noqa: B010
            raise

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
            self._notify(
                self.loc_manager.tr(
                    "Download.Notify.SuccessTitle", "Download Complete"
                ),
                msg_text,
                icon_type="success",
            )

            QTimer.singleShot(400, lambda mk=mode_key: self._set_to_uptodate_state(mk))
        else:
            self.download_button.reset_progress()
            self._notify(
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

    def _set_to_uptodate_state(self, mode_key: str | None = None):
        """Helper method to set the final UI state."""
        if mode_key is not None and mode_key != self.get_mode().key:
            logger.info(
                f"Discarding stale up-to-date timer for '{mode_key}'; "
                f"active mode is '{self.get_mode().key}'."
            )
            return

        self.download_button.reset_progress()
        self.download_button.setText(
            self.loc_manager.tr("Download.Btn.UpToDate", "Up-to-date")
        )
        self.download_button.setEnabled(False)
        self.is_download_ready = False
