# main_window.py - Main application window with sidebar navigation.
import logging
import os
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import menu_modes
import update_checker
from menu_modes import get_mode
from paths import resource_path
from ui.pages.download_page import DownloadPage
from ui.pages.inject_page import InjectPage
from ui.pages.risk_page import RiskPage
from ui.pages.settings_page import SettingsPage
from ui.widgets.buttons import StatefulButton
from ui.widgets.notifications import NotificationManager
from ui.widgets.toggle_switch import ToggleSwitch
from ymu_config import get_config

if TYPE_CHECKING:
    from localization_manager import LocalizationManager
    from theme_manager import ThemeManager
    from worker_manager import WorkerManager

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    mode_changed = Signal(object)  # emits the new MenuMode

    def __init__(
        self,
        theme_manager: "ThemeManager",
        worker_manager: "WorkerManager",
        loc_manager: "LocalizationManager",
    ):
        super().__init__()
        self._is_ready_to_show = False
        self.setWindowOpacity(0.0)
        self.theme_manager = theme_manager
        self.worker_manager = worker_manager
        self.loc_manager = loc_manager
        self.config = get_config()
        self.current_mode = get_mode(self.config.get("mode", "legacy"))
        self._autodetect_message: str | None = None
        self._maybe_autodetect_edition()
        self.notification_manager = NotificationManager(self, self.theme_manager)

        self.setWindowTitle("YimMenuUpdater | NV3")
        self.setFixedSize(QSize(780, 520))

        main_widget = QWidget()
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar_widget = QWidget()
        sidebar_widget.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(sidebar_widget)
        sidebar_widget.setFixedWidth(200)

        self.content_stack = QStackedWidget()

        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(main_widget)

        get_active_mode = lambda: self.current_mode

        self.risk_page = RiskPage(
            theme_manager=self.theme_manager, loc_manager=self.loc_manager
        )
        self.download_page = DownloadPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=get_active_mode,
        )
        self.inject_page = InjectPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=get_active_mode,
        )
        self.settings_page = SettingsPage(
            theme_manager=self.theme_manager,
            worker_manager=self.worker_manager,
            loc_manager=self.loc_manager,
            get_mode=get_active_mode,
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

    def show_when_ready(self):
        """Signals that the app is initialized and triggers the first paint."""
        self._is_ready_to_show = True
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
        self.button_group = QButtonGroup()
        self.button_group.setExclusive(True)
        self.button_group.buttonClicked.connect(
            lambda: QTimer.singleShot(
                0,
                lambda: [
                    b.updateIcon()
                    for b in self.button_group.buttons()
                    if isinstance(b, StatefulButton)
                ],
            )
        )

        sidebar_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
            "color_checked": ("#E0E0E0", "#121212"),
        }

        btn_risks = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Risks')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "alert-triangle.svg")
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
            icon_path=resource_path(os.path.join("assets", "icons", "crosshair.svg")),
            **sidebar_colors,
        )
        btn_inject.setCheckable(True)
        btn_inject.setObjectName("SidebarButton")

        btn_settings = StatefulButton(
            f"  {self.loc_manager.tr('Sidebar.Settings')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "settings.svg")),
            **sidebar_colors,
        )
        btn_settings.setCheckable(True)
        btn_settings.setObjectName("SidebarButton")

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

        footer_button = StatefulButton(
            f"YMU {update_checker.LOCAL_VERSION}\n© NiiV3AU",
            theme_manager=self.theme_manager,
        )
        footer_button.setObjectName("SidebarFooter")
        footer_button.clicked.connect(lambda: webbrowser.open("https://ymu.pages.dev/"))
        footer_button.setToolTip(
            self.loc_manager.tr(
                "Sidebar.Tooltip.ProjectPage",
                "Open the YMU project page in your browser",
            )
        )

        layout.addWidget(footer_button)

        btn_risks.setChecked(True)

        btn_risks.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.risk_page)
        )
        btn_download.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.download_page)
        )
        btn_inject.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.inject_page)
        )
        btn_settings.clicked.connect(
            lambda: self.content_stack.setCurrentWidget(self.settings_page)
        )

    def show_download_page(self):
        """Navigate to the Download page as if the sidebar button was clicked,
        so the page switch, the selected-button highlight and its icon all stay
        in sync. Used by the 'Re-download DLL' action on injection errors."""
        self.btn_download.click()

    def show_risks_page(self):
        """Navigate to the Risks page (which explains how to disable BattlEye),
        keeping the sidebar selection in sync."""
        self.btn_risks.click()

    def _setup_mode_switch(self, layout: QVBoxLayout):
        """Builds the Legacy/Enhanced edition switch at the bottom of the sidebar."""
        mode_frame = QFrame()
        mode_frame.setObjectName("ModeSwitchFrame")
        mode_layout = QHBoxLayout(mode_frame)
        mode_layout.setContentsMargins(10, 4, 10, 4)

        self.mode_legacy_label = QLabel(
            self.loc_manager.tr("Sidebar.Mode.Legacy", "Legacy")
        )
        self.mode_enhanced_label = QLabel(
            self.loc_manager.tr("Sidebar.Mode.Enhanced", "E&E")
        )

        self.mode_toggle = ToggleSwitch(variant="sidebar")
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
        self.theme_manager.themeChanged.connect(lambda _t: self._update_mode_labels())

    def _update_mode_labels(self):
        """Highlights the active edition so the current mode is unambiguous.
        The active edition uses the plain foreground colour (no accent) so the
        switch stays visually calm; the inactive one is muted but still legible.
        The bold/normal weight change is kept as a second, colour-independent
        cue."""
        if self.theme_manager.current_theme == "light":
            active = "font-weight: bold; color: #1A1D21;"
            inactive = "color: #A6ACB4;"
        else:
            active = "font-weight: bold; color: #FFFFFF;"
            inactive = "color: #777777;"
        is_enhanced = self.current_mode.key == "enhanced"
        self.mode_legacy_label.setStyleSheet(inactive if is_enhanced else active)
        self.mode_enhanced_label.setStyleSheet(active if is_enhanced else inactive)

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
