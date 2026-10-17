import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from core import menu_modes, update_checker
from core.config import get_config
from core.menu_modes import get_mode
from core.paths import WINDOW_TITLE, resource_path
from ui.pages.download_page import DownloadPage
from ui.pages.inject_page import InjectPage
from ui.pages.risk_page import RiskPage
from ui.pages.settings_page import SettingsPage
from ui.utils import update_app_icon
from ui.widgets import (
    AboutDialog,
    AnimatedStackedWidget,
    NotificationManager,
    SidebarIndicator,
    StatefulButton,
    ToggleSwitch,
)

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    mode_changed = Signal(object)  # emits the new MenuMode

    def __init__(
        self,
        theme_manager: "ThemeManager",
        worker_manager: "WorkerManager",
        loc_manager: "LocalizationManager",
        auto_check: bool = True,
    ):
        super().__init__()
        self._is_ready_to_show = False
        self.setWindowOpacity(0.0)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self.config = get_config()
        self.config.save_failed.connect(self._on_config_save_failed)
        self.current_mode = get_mode(self.config.get("mode", "legacy"))
        self._autodetect_message: str | None = None
        self._maybe_autodetect_edition()
        self.notification_manager = NotificationManager(self, self.theme_manager)

        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(QSize(860, 520))

        self.main_widget = QWidget()
        main_layout = QHBoxLayout(self.main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar_widget = QWidget()
        self.sidebar_widget.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_widget.setFixedWidth(200)

        self.content_stack = AnimatedStackedWidget(
            duration=240, orientation=Qt.Orientation.Vertical
        )

        main_layout.addWidget(self.sidebar_widget)
        main_layout.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(self.main_widget)

        self.risk_page = RiskPage(
            theme_manager=self.theme_manager, loc_manager=self.loc_manager
        )
        self.download_page = DownloadPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=self.get_active_mode,
            auto_check=auto_check,
        )
        self.inject_page = InjectPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=self.get_active_mode,
        )
        self.settings_page = SettingsPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=self.get_active_mode,
        )

        self.mode_changed.connect(self.download_page.on_mode_changed)
        self.mode_changed.connect(self.inject_page.on_mode_changed)
        self.mode_changed.connect(self.settings_page.on_mode_changed)

        self.content_stack.addWidget(self.risk_page)
        self.content_stack.addWidget(self.download_page)
        self.content_stack.addWidget(self.inject_page)
        self.content_stack.addWidget(self.settings_page)

        self.setup_sidebar(sidebar_layout)

        # Cards get real elevation from a soft drop shadow in the light theme
        # (Qt QSS has no box-shadow). Reapply whenever the theme changes.
        self.theme_manager.themeChanged.connect(self._apply_card_shadows)
        self._apply_card_shadows(self.theme_manager.current_theme)

        self.loc_manager.layout_direction_changed.connect(
            self._on_layout_direction_changed
        )

    @Slot(object)
    def _on_layout_direction_changed(self, new_direction: Qt.LayoutDirection):
        """Synchronizes global layout direction and theme overrides on language changes."""
        if QApplication.layoutDirection() != new_direction:
            QApplication.setLayoutDirection(new_direction)
        if self.layoutDirection() != new_direction:
            self.setLayoutDirection(new_direction)
        is_rtl = new_direction == Qt.LayoutDirection.RightToLeft
        self.theme_manager.set_rtl(is_rtl)
        self.notification_manager.reposition_notifications()
        self._update_mode_labels()
        if hasattr(self, "sidebar_indicator"):
            self.sidebar_indicator.sync_to_current()
            self.sidebar_indicator.update()

    @Slot(str)
    def _apply_card_shadows(self, theme: str):
        """Gives every card a soft drop shadow in the light theme, where flat
        light fills lack depth. In the dark theme the shadow would be invisible
        on the near-black surface, so it is disabled; Qt bypasses a disabled
        effect entirely, so the card and its animations render at no cost. The
        effect is created once per card; afterwards only its enabled flag is
        toggled."""
        for card in self.findChildren(QFrame):
            if card.objectName() != "CardFrame":
                continue
            effect = card.graphicsEffect()
            if not isinstance(effect, QGraphicsDropShadowEffect):
                effect = QGraphicsDropShadowEffect(card)
                effect.setBlurRadius(24)
                effect.setOffset(0, 4)
                effect.setColor(QColor(60, 70, 90, 40))
                card.setGraphicsEffect(effect)
            effect.setEnabled(theme == "light")

    @Slot()
    def show_when_ready(self):
        """Signals that the app is initialized and triggers the first paint."""
        self._is_ready_to_show = True
        focused = QApplication.focusWidget()
        if focused:
            focused.clearFocus()
        if hasattr(self, "sidebar_indicator"):
            self.sidebar_indicator.sync_to_current()
            self.sidebar_indicator.show()
            self.sidebar_indicator.lower()
        self.update()

        if self._autodetect_message:
            self.notification_manager.show(
                self.loc_manager.tr("Common.Info", "Information"),
                self._autodetect_message,
                icon_type="info",
                duration=8000,
            )
            self._autodetect_message = None

    def paintEvent(self, event):
        """Called every time the window needs to be repainted."""
        super().paintEvent(event)

        if self._is_ready_to_show and self.windowOpacity() == 0.0:
            self.setWindowOpacity(1.0)

    def setup_sidebar(self, layout: QVBoxLayout):
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(self._on_sidebar_button_clicked)

        sidebar_parent = layout.parentWidget()
        if sidebar_parent:
            self.sidebar_indicator = SidebarIndicator(
                sidebar_parent, self.theme_manager
            )
            self.sidebar_indicator.lower()
            self.button_group.buttonClicked.connect(self._on_sidebar_indicator_move)

        sidebar_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
            "color_checked": ("#E0E0E0", "#121212"),
        }

        btn_risks = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Risks')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "triangle-alert.svg")
            ),
            **sidebar_colors,
        )
        btn_risks.setCheckable(True)
        btn_risks.setObjectName("SidebarButton")
        btn_risks.setToolTip(
            self.loc_manager.tr(
                "Sidebar.Tooltip.Risks", "Show important warnings and information"
            )
        )
        # Kept as an attribute so pages can navigate here programmatically
        # (e.g. the "How to disable" action on a BattlEye injection warning).
        self.btn_risks = btn_risks

        btn_download = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Download')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "download.svg")),
            **sidebar_colors,
        )
        btn_download.setCheckable(True)
        btn_download.setObjectName("SidebarButton")
        # Kept as an attribute so other pages can navigate here programmatically
        # (e.g. the "Re-download DLL" action on an injection error).
        self.btn_download = btn_download

        btn_inject = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Inject')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "syringe.svg")),
            **sidebar_colors,
        )
        btn_inject.setCheckable(True)
        btn_inject.setObjectName("SidebarButton")
        self.btn_inject = btn_inject

        btn_settings = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Settings')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "settings.svg")),
            **sidebar_colors,
        )
        btn_settings.setCheckable(True)
        btn_settings.setObjectName("SidebarButton")
        self.btn_settings = btn_settings

        layout.addWidget(btn_risks)
        self.button_group.addButton(btn_risks)
        layout.addWidget(btn_download)
        self.button_group.addButton(btn_download)
        layout.addWidget(btn_inject)
        self.button_group.addButton(btn_inject)
        layout.addWidget(btn_settings)
        self.button_group.addButton(btn_settings)
        layout.addStretch()

        self._setup_mode_switch(layout)

        self.footer_button = StatefulButton(
            f"YMU {update_checker.LOCAL_VERSION}\n© NiiV3AU",
            theme_manager=self.theme_manager,
        )
        self.footer_button.setObjectName("SidebarFooter")
        self.footer_button.clicked.connect(self.show_about_dialog)
        self.footer_button.setToolTip(
            self.loc_manager.tr(
                "About.Tooltip",
                "View project information, dependencies, and open-source licenses",
            )
        )

        layout.addWidget(self.footer_button)

        self.setTabOrder(btn_risks, btn_download)
        self.setTabOrder(btn_download, btn_inject)
        self.setTabOrder(btn_inject, btn_settings)
        self.setTabOrder(btn_settings, self.mode_toggle)
        self.setTabOrder(self.mode_toggle, self.footer_button)

        btn_risks.setChecked(True)
        if hasattr(self, "sidebar_indicator"):
            self.sidebar_indicator.move_to_button(btn_risks, animate=False)

        btn_risks.clicked.connect(self._show_risk_page)
        btn_download.clicked.connect(self._show_download_page)
        btn_inject.clicked.connect(self._show_inject_page)
        btn_settings.clicked.connect(self._show_settings_page)

    @Slot()
    def show_about_dialog(self):
        """Displays the modal About and Open Source Licenses dialog."""
        dialog = AboutDialog(
            theme_manager=self.theme_manager,
            loc_manager=self.loc_manager,
            parent=self,
        )
        dialog.exec()

    @Slot()
    def show_download_page(self):
        """Navigate to the Download page as if the sidebar button was clicked,
        so the page switch, the selected-button highlight and its icon all stay
        in sync. Used by the 'Re-download DLL' action on injection errors."""
        self.btn_download.click()

    @Slot()
    def show_risks_page(self):
        """Navigate to the Risks page (which explains how to disable BattlEye),
        keeping the sidebar selection in sync."""
        self.btn_risks.click()

    def _setup_mode_switch(self, layout: QVBoxLayout):
        """Builds the Legacy/Enhanced edition switch at the bottom of the sidebar."""
        mode_frame = QFrame()
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(10, 4, 10, 4)

        self.mode_legacy_label = QLabel(
            self.loc_manager.tr("Sidebar.Mode.Legacy", "Legacy")
        )
        self.mode_enhanced_label = QLabel(
            self.loc_manager.tr("Sidebar.Mode.Enhanced", "E&E")
        )

        self.mode_toggle = ToggleSwitch(
            variant="sidebar", theme_manager=self.theme_manager
        )
        self.mode_toggle.setToolTip(
            self.loc_manager.tr(
                "Sidebar.Mode.Tooltip",
                "Switch between YimMenu (Legacy) and YimMenuV2 (Enhanced)",
            )
        )

        mode_layout.addWidget(self.mode_legacy_label)
        mode_layout.addStretch()
        mode_layout.addWidget(self.mode_toggle)
        mode_layout.addStretch()
        mode_layout.addWidget(self.mode_enhanced_label)

        layout.addWidget(mode_frame)

        self.mode_toggle.blockSignals(True)
        self.mode_toggle.setChecked(self.current_mode.key == "enhanced")
        self.mode_toggle.blockSignals(False)
        self._update_mode_labels()

        self.mode_toggle.toggled.connect(self._on_mode_toggled)
        # Label colours depend on the theme, and inline styles do not restyle
        # automatically, so refresh them whenever the theme changes.
        self.theme_manager.themeChanged.connect(
            self._on_theme_changed_update_mode_labels
        )

    @Slot(str)
    def _on_theme_changed_update_mode_labels(self, _theme: str | None = None):
        self._update_mode_labels()

    def _update_mode_labels(self):
        """Highlights the active edition so the current mode is unambiguous.
        The active edition uses the plain foreground colour (no accent) so the
        switch stays visually calm; the inactive one is muted but still legible.
        The bold/normal weight change is kept as a second, colour-independent
        cue."""
        if self.theme_manager.current_theme == "light":
            active = "font-weight: 600; color: #1A1D21;"
            inactive = "color: #A6ACB4;"
        else:
            active = "font-weight: 600; color: #FFFFFF;"
            inactive = "color: #777777;"
        is_enhanced = self.current_mode.key == "enhanced"
        self.mode_legacy_label.setStyleSheet(inactive if is_enhanced else active)
        self.mode_enhanced_label.setStyleSheet(active if is_enhanced else inactive)

    @Slot(bool)
    def _on_mode_toggled(self, checked: bool):
        """Persists the new mode and notifies all pages."""
        key = "enhanced" if checked else "legacy"
        # A manual toggle is an explicit choice: stop auto-detecting from now on.
        self.config.set("mode_user_set", True)
        if key == self.current_mode.key:
            return
        self.current_mode = get_mode(key)
        self.config.set("mode", key)
        self._update_mode_labels()
        logger.info(f"Mode switched to: {self.current_mode.display_name}")
        self.mode_changed.emit(self.current_mode)

    def _maybe_autodetect_edition(self):
        """On first run (before the user has ever picked an edition), select the
        installed edition automatically so most users never touch the toggle.
        Runs synchronously — it is only a couple of fast registry reads."""
        if self.config.get("mode_user_set", False):
            return
        try:
            detected = menu_modes.detect_installed_modes()
        except OSError as e:
            logger.warning(f"Edition auto-detection failed: {e}")
            return

        if len(detected) == 1 and detected[0] != self.current_mode.key:
            new_mode = get_mode(detected[0])
            logger.info(
                f"Auto-detected {new_mode.display_name}; selecting it automatically."
            )
            self.current_mode = new_mode
            self.config.set("mode", new_mode.key)
            self._autodetect_message = self.loc_manager.tr(
                "Sidebar.Mode.AutoDetected",
                "Detected {0} — selected it automatically.\n"
                "Use the sidebar switch to change it.",
            ).format(new_mode.display_name)
        elif len(detected) > 1:
            logger.info("Both GTA V editions detected; keeping the saved mode.")

    @Slot(str, str)
    def _on_config_save_failed(self, key_path: str, error_msg: str) -> None:
        logger.error(f"Failed to persist config key '{key_path}' to disk: {error_msg}")
        self.notification_manager.show(
            self.loc_manager.tr("Common.Error", "Error"),
            self.loc_manager.tr(
                "Common.Notify.ConfigSaveFailed",
                "Failed to save setting to disk.",
            ),
            icon_type="error",
        )

    def get_active_mode(self):
        return self.current_mode

    @Slot()
    def _on_sidebar_button_clicked(self) -> None:
        QTimer.singleShot(0, self._update_sidebar_icons)

    @Slot()
    def _update_sidebar_icons(self) -> None:
        for b in self.button_group.buttons():
            if isinstance(b, StatefulButton):
                b.updateIcon()

    @Slot(object)
    def _on_sidebar_indicator_move(self, btn: object) -> None:
        if hasattr(self, "sidebar_indicator") and isinstance(btn, QAbstractButton):
            self.sidebar_indicator.move_to_button(btn, animate=True)

    @Slot()
    def _show_risk_page(self) -> None:
        self.content_stack.setCurrentWidget(self.risk_page)

    @Slot()
    def _show_download_page(self) -> None:
        self.content_stack.setCurrentWidget(self.download_page)

    @Slot()
    def _show_inject_page(self) -> None:
        self.content_stack.setCurrentWidget(self.inject_page)

    @Slot()
    def _show_settings_page(self) -> None:
        self.content_stack.setCurrentWidget(self.settings_page)

    @Slot()
    def on_system_color_scheme_changed(self) -> None:
        app = QApplication.instance()
        if isinstance(app, QApplication):
            update_app_icon(app, self)

    def closeEvent(self, event: QCloseEvent):
        """Cleanly handle application window closing."""
        logger.info("MainWindow closeEvent received; shutting down background workers.")
        if not self.worker_manager.cleanup(timeout_ms=1000):
            logger.warning(
                "WorkerManager did not finish all background tasks within closeEvent budget."
            )
        self.hide()
        event.accept()
