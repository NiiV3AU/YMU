# settings_page.py - Settings UI for theme, language, lua scripts, paths, and updates.
import logging
import os
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import lua_manager, process_manager, update_checker
from core import settings as settings_manager
from core.config import get_config
from core.menu_modes import MenuMode
from core.paths import YMU_APPDATA_DIR, resource_path
from ui.utils import restart_application
from ui.widgets.buttons import AnimatedButton, StatefulButton
from ui.widgets.toggle_switch import ToggleSwitch

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class SettingsPage(QWidget):
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
        self._is_task_running = False

        scroll_content_widget = QWidget()
        scroll_content_widget.setObjectName("ScrollContainer")
        content_layout = QVBoxLayout(scroll_content_widget)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        appearance_frame = QFrame()
        appearance_frame.setObjectName("CardFrame")
        appearance_layout = QVBoxLayout(appearance_frame)

        appearance_title = QLabel(
            self.loc_manager.tr("Settings.Header.Appearance", "Appearance")
        )
        appearance_title.setObjectName("SettingsTitle")

        theme_button_layout = QHBoxLayout()
        self.theme_group = QButtonGroup()
        self.theme_group.setExclusive(True)

        btn_dark_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Dark', 'Dark')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "moon.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        btn_dark_theme.setObjectName("ThemeButton")
        btn_dark_theme.setCheckable(True)

        btn_light_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Light', 'Light')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "sun.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        btn_light_theme.setObjectName("ThemeButton")
        btn_light_theme.setCheckable(True)

        self.theme_group.addButton(btn_dark_theme)
        self.theme_group.addButton(btn_light_theme)

        if self.theme_manager.current_theme == "light":
            btn_light_theme.setChecked(True)
        else:
            btn_dark_theme.setChecked(True)

        self.theme_group.buttonClicked.connect(
            lambda: QTimer.singleShot(
                0,
                lambda: [
                    b.updateIcon()
                    for b in self.theme_group.buttons()
                    if isinstance(b, StatefulButton)
                ],
            )
        )
        btn_dark_theme.clicked.connect(lambda: self.theme_manager.apply_theme("dark"))
        btn_light_theme.clicked.connect(lambda: self.theme_manager.apply_theme("light"))

        theme_button_layout.addWidget(btn_dark_theme)
        theme_button_layout.addWidget(btn_light_theme)

        lang_layout = QHBoxLayout()
        lang_label = QLabel(self.loc_manager.tr("Settings.Label.Language", "Language"))

        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_combo.setFixedWidth(150)
        self.lang_combo.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.Language",
                "Select application language (requires restart)",
            )
        )

        available_locales = self.loc_manager.get_available_locales()

        for code in available_locales:
            display_name = self.loc_manager.get_language_name(code)
            self.lang_combo.addItem(display_name, code)

            if code == self.loc_manager.active_locale:
                self.lang_combo.setCurrentIndex(self.lang_combo.count() - 1)

        self._lang_debounce_timer = QTimer()
        self._lang_debounce_timer.setSingleShot(True)
        self._lang_debounce_timer.setInterval(250)
        self._lang_debounce_timer.timeout.connect(self._commit_language_change)

        self.btn_update_lang = AnimatedButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "download-cloud.svg")
            ),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.btn_update_lang.setObjectName("RefreshButton")
        self.btn_update_lang.setFixedSize(32, 32)
        self.btn_update_lang.setIconSize(QSize(20, 20))
        self.btn_update_lang.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.UpdateLang", "Check for translation updates"
            )
        )

        self.btn_update_lang.clicked.connect(self._on_fetch_lang_clicked)
        self.loc_manager.update_finished.connect(self._on_lang_fetch_finished)
        self.lang_combo.currentIndexChanged.connect(
            lambda: self._lang_debounce_timer.start()
        )
        lang_layout.addWidget(lang_label)
        lang_layout.addStretch()
        lang_layout.addWidget(self.btn_update_lang)
        lang_layout.addSpacing(10)
        lang_layout.addWidget(self.lang_combo)

        appearance_layout.addWidget(appearance_title)
        appearance_layout.addLayout(theme_button_layout)
        appearance_layout.addSpacing(10)
        appearance_layout.addLayout(lang_layout)

        color_normal_lua = ("#8B8B8B", "#555555")
        color_hover_lua = ("#E0E0E0", "#121212")
        lua_frame = QFrame()
        lua_frame.setObjectName("CardFrame")
        lua_layout = QVBoxLayout(lua_frame)

        lua_title = QLabel(self.loc_manager.tr("Settings.Header.Lua", "Lua Settings"))
        lua_title.setObjectName("SettingsTitle")

        auto_reload_layout = QHBoxLayout()
        self.auto_reload_label = QLabel(
            self.loc_manager.tr(
                "Settings.Lua.AutoReload", "Auto-reload changed scripts"
            )
        )
        self.auto_reload_toggle = ToggleSwitch()
        self.auto_reload_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.AutoReload",
                "Automatically re-apply changes when Lua script files are saved",
            )
        )

        auto_reload_layout.addWidget(self.auto_reload_label)
        auto_reload_layout.addStretch()
        auto_reload_layout.addWidget(self.auto_reload_toggle)

        lua_layout.addWidget(lua_title)
        lua_layout.addLayout(auto_reload_layout)

        self.lua_hint_label = QLabel("")
        self.lua_hint_label.setObjectName("RiskInfoLabel")
        self.lua_hint_label.setWordWrap(True)
        self.lua_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lua_hint_label.setVisible(False)
        lua_layout.addWidget(self.lua_hint_label)

        manager_grid_layout = QGridLayout()

        disabled_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListDisabled", "Disabled")
        )
        disabled_label.setObjectName("DisabledListHeader")
        enabled_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListEnabled", "Enabled")
        )
        enabled_label.setObjectName("EnabledListHeader")

        manager_grid_layout.addWidget(disabled_label, 0, 0)
        manager_grid_layout.addWidget(enabled_label, 0, 2)

        self.disabled_scripts_list = QListWidget()
        self.disabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.enabled_scripts_list = QListWidget()
        self.enabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        manager_grid_layout.addWidget(self.disabled_scripts_list, 1, 0)
        manager_grid_layout.addWidget(self.enabled_scripts_list, 1, 2)

        buttons_layout = QVBoxLayout()
        buttons_layout.addStretch()

        self.btn_enable_script = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "chevron-right.svg")
            ),
            color_normal=color_normal_lua,
            color_hover=("#FFFFFF", "#FFFFFF"),
        )
        self.btn_enable_script.setObjectName("EnableButton")
        self.btn_enable_script.setIconSize(QSize(20, 20))
        self.btn_enable_script.setFixedSize(36, 36)
        self.btn_enable_script.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.Enable", "Enable selected script(s)"
            )
        )

        self.btn_refresh_luas = AnimatedButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "refresh-cw.svg")),
            color_normal=color_normal_lua,
            color_hover=color_hover_lua,
        )
        self.btn_refresh_luas.setObjectName("RefreshButton")
        self.btn_refresh_luas.setIconSize(QSize(20, 20))
        self.btn_refresh_luas.setFixedSize(36, 36)
        self.btn_refresh_luas.setToolTip(
            self.loc_manager.tr("Settings.Lua.Tooltip.Refresh", "Refresh script lists")
        )

        self.btn_disable_script = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "chevron-left.svg")
            ),
            color_normal=color_normal_lua,
            color_hover=("#FFFFFF", "#FFFFFF"),
        )
        self.btn_disable_script.setObjectName("DisableButton")
        self.btn_disable_script.setIconSize(QSize(20, 20))
        self.btn_disable_script.setFixedSize(36, 36)
        self.btn_disable_script.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.Disable", "Disable selected script(s)"
            )
        )

        buttons_layout.addWidget(self.btn_enable_script)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.btn_refresh_luas)
        buttons_layout.addSpacing(10)
        buttons_layout.addWidget(self.btn_disable_script)
        buttons_layout.addStretch()

        manager_grid_layout.addLayout(buttons_layout, 1, 1)
        manager_grid_layout.setColumnStretch(0, 4)
        manager_grid_layout.setColumnStretch(1, 1)
        manager_grid_layout.setColumnStretch(2, 4)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }
        footer_layout = QHBoxLayout()
        btn_open_scripts_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenScripts', 'Open Scripts Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_scripts_folder.setObjectName("LinkButton")
        btn_open_scripts_folder.setIconSize(QSize(20, 20))
        btn_open_scripts_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenScripts",
                "Open the folder where your Lua scripts are located",
            )
        )

        btn_discover_luas = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.DiscoverLua', 'Discover Luas')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "compass.svg")),
            **link_button_colors,
        )
        btn_discover_luas.setObjectName("LinkButton")
        btn_discover_luas.setIconSize(QSize(20, 20))
        btn_discover_luas.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.DiscoverLua",
                "Open the official YimMenu-Lua GitHub organization to find new scripts",
            )
        )

        footer_layout.addWidget(btn_open_scripts_folder)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_discover_luas)

        lua_layout.addSpacing(15)
        lua_layout.addLayout(manager_grid_layout)
        lua_layout.addSpacing(10)
        lua_layout.addLayout(footer_layout)

        self.setTabOrder(self.auto_reload_toggle, self.disabled_scripts_list)
        self.setTabOrder(self.disabled_scripts_list, self.btn_enable_script)
        self.setTabOrder(self.btn_enable_script, self.btn_refresh_luas)
        self.setTabOrder(self.btn_refresh_luas, self.btn_disable_script)
        self.setTabOrder(self.btn_disable_script, self.enabled_scripts_list)
        self.setTabOrder(self.enabled_scripts_list, btn_open_scripts_folder)
        self.setTabOrder(btn_open_scripts_folder, btn_discover_luas)

        other_frame = QFrame()
        other_frame.setObjectName("CardFrame")
        other_layout = QVBoxLayout(other_frame)

        other_title = QLabel(self.loc_manager.tr("Settings.Header.Other", "Other"))
        other_title.setObjectName("SettingsTitle")

        debug_console_layout = QHBoxLayout()
        self.debug_console_label = QLabel(
            self.loc_manager.tr(
                "Settings.Other.DebugConsole", "Enable External Debug Console"
            )
        )
        self.debug_console_toggle = ToggleSwitch()
        self.debug_console_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Other.Tooltip.Debug",
                "Show YimMenu's external console window for detailed logs and debugging",
            )
        )
        debug_console_layout.addWidget(self.debug_console_label)
        debug_console_layout.addStretch()
        debug_console_layout.addWidget(self.debug_console_toggle)

        btn_open_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYimFolder', 'Open YimMenu Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_folder.setObjectName("LinkButton")
        btn_open_folder.setIconSize(QSize(20, 20))
        btn_open_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYimFolder",
                "Open YimMenu folder (%APPDATA%/YimMenu)",
            )
        )

        btn_open_ymu_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYmuFolder', 'Open YMU Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_open_ymu_folder.setObjectName("LinkButton")
        btn_open_ymu_folder.setIconSize(QSize(20, 20))
        btn_open_ymu_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYmuFolder", "Open YMU folder (%APPDATA%/YMU)"
            )
        )

        btn_report_bug = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.ReportBug', 'Report a Bug')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        btn_report_bug.setObjectName("LinkButton")
        btn_report_bug.setIconSize(QSize(20, 20))
        btn_report_bug.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.ReportBug",
                "Open the bug report page on GitHub in your browser",
            )
        )

        btn_request_feature = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.RequestFeature', 'Request a Feature')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        btn_request_feature.setObjectName("LinkButton")
        btn_request_feature.setIconSize(QSize(20, 20))
        btn_request_feature.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.RequestFeature",
                "Open the feature request page on GitHub in your browser",
            )
        )
        self.btn_check_for_updates = AnimatedButton(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates"),
            theme_manager=self.theme_manager,
        )
        other_layout.addWidget(other_title)
        other_layout.addLayout(debug_console_layout)
        other_layout.addWidget(btn_open_folder)
        other_layout.addWidget(btn_open_ymu_folder)
        other_layout.addWidget(btn_report_bug)
        other_layout.addWidget(btn_request_feature)
        other_layout.addSpacing(15)
        other_layout.addWidget(
            self.btn_check_for_updates, alignment=Qt.AlignmentFlag.AlignCenter
        )

        paths_frame = self._build_paths_frame()
        injection_frame = self._build_injection_frame()

        content_layout.addWidget(appearance_frame)
        content_layout.addWidget(lua_frame)
        content_layout.addWidget(paths_frame)
        content_layout.addWidget(injection_frame)
        content_layout.addWidget(other_frame)
        content_layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("SettingsScrollArea")
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(scroll_content_widget)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(scroll_area)

        btn_open_folder.clicked.connect(
            lambda: self._open_link(self.get_mode().appdata_dir)
        )
        btn_open_ymu_folder.clicked.connect(lambda: self._open_link(YMU_APPDATA_DIR))

        btn_report_bug.clicked.connect(
            lambda: self._open_link(
                "https://github.com/NiiV3AU/YMU/issues/new?template=bug_report.yaml"
            )
        )
        btn_request_feature.clicked.connect(
            lambda: self._open_link(
                "https://github.com/NiiV3AU/YMU/issues/new?template=feature_request.yaml"
            )
        )
        self.btn_check_for_updates.clicked.connect(self._handle_check_for_updates)
        self.auto_reload_toggle.toggled.connect(self._on_auto_reload_toggled)
        self.debug_console_toggle.toggled.connect(self._on_debug_console_toggled)
        self.auto_reload_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.auto_reload_label, has_focus
            )
        )
        self.debug_console_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.debug_console_label, has_focus
            )
        )
        self.btn_enable_script.clicked.connect(self._enable_selected_scripts)
        self.btn_disable_script.clicked.connect(self._disable_selected_scripts)
        btn_open_scripts_folder.clicked.connect(
            lambda: self._open_link(self.get_mode().scripts_dir)
        )
        self.btn_refresh_luas.clicked.connect(self._refresh_lua_lists)
        btn_discover_luas.clicked.connect(
            lambda: self._open_link("https://github.com/orgs/YimMenu-Lua/repositories")
        )

        self.setTabOrder(btn_discover_luas, self.gta_dir_edit)
        self.setTabOrder(self.btn_clear_dll, self.nobattleye_toggle)
        self.setTabOrder(self.nobattleye_toggle, self.auto_close_toggle)
        self.setTabOrder(self.auto_close_toggle, self.sound_feedback_toggle)
        self.setTabOrder(self.sound_feedback_toggle, self.debug_console_toggle)

        self._refresh_lua_lists()
        self._load_initial_settings()

    def on_mode_changed(self, mode: MenuMode):
        """Slot: the sidebar switch changed the active edition."""
        self._refresh_lua_lists()
        self._load_initial_settings()
        self._update_nobattleye_toggle_state()

    def _notify(self, title: str, message: str, **kwargs):
        win = self.window()
        if win and hasattr(win, "notification_manager"):
            win.notification_manager.show(title, message, **kwargs)

    def _build_paths_frame(self) -> QFrame:
        """Custom GTA V install path and custom DLL (issue #19)."""
        config = get_config()
        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }

        frame = QFrame()
        frame.setObjectName("CardFrame")
        layout = QVBoxLayout(frame)

        title = QLabel(self.loc_manager.tr("Settings.Header.Paths", "Custom Paths"))
        title.setObjectName("SettingsTitle")
        layout.addWidget(title)

        # --- GTA V install directory row ---
        gta_label = QLabel(
            self.loc_manager.tr("Settings.Paths.GtaDir", "GTA V install folder")
        )
        self.gta_dir_edit = QLineEdit()
        self.gta_dir_edit.setReadOnly(True)
        self.gta_dir_edit.setPlaceholderText(
            self.loc_manager.tr("Settings.Paths.AutoDetect", "Auto-detected")
        )
        self.gta_dir_edit.setText(config.get("paths.gta_dir") or "")

        btn_browse_gta = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Browse', 'Browse')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_browse_gta.setObjectName("LinkButton")
        btn_clear_gta = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Clear', 'Clear')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "trash.svg")),
            **link_button_colors,
        )
        btn_clear_gta.setObjectName("LinkButton")
        btn_browse_gta.clicked.connect(self._browse_gta_dir)
        btn_clear_gta.clicked.connect(lambda: self._clear_path("paths.gta_dir"))

        gta_row = QHBoxLayout()
        gta_row.addWidget(self.gta_dir_edit, stretch=1)
        gta_row.addWidget(btn_browse_gta)
        gta_row.addWidget(btn_clear_gta)

        layout.addWidget(gta_label)
        layout.addLayout(gta_row)

        # --- Custom DLL row ---
        dll_label = QLabel(
            self.loc_manager.tr("Settings.Paths.CustomDll", "Custom menu DLL")
        )
        self.custom_dll_edit = QLineEdit()
        self.custom_dll_edit.setReadOnly(True)
        self.custom_dll_edit.setPlaceholderText(
            self.loc_manager.tr("Settings.Paths.DefaultDll", "Use downloaded DLL")
        )
        self.custom_dll_edit.setText(config.get("paths.custom_dll") or "")

        btn_browse_dll = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Browse', 'Browse')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder.svg")),
            **link_button_colors,
        )
        btn_browse_dll.setObjectName("LinkButton")
        self.btn_clear_dll = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Clear', 'Clear')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "trash.svg")),
            **link_button_colors,
        )
        self.btn_clear_dll.setObjectName("LinkButton")
        btn_browse_dll.clicked.connect(self._browse_custom_dll)
        self.btn_clear_dll.clicked.connect(lambda: self._clear_path("paths.custom_dll"))

        dll_row = QHBoxLayout()
        dll_row.addWidget(self.custom_dll_edit, stretch=1)
        dll_row.addWidget(btn_browse_dll)
        dll_row.addWidget(self.btn_clear_dll)

        layout.addSpacing(10)
        layout.addWidget(dll_label)
        layout.addLayout(dll_row)

        # --- BattlEye commandline.txt row ---
        nobattleye_row = QHBoxLayout()
        self.nobattleye_label = QLabel(
            self.loc_manager.tr(
                "Settings.Paths.NoBattlEye", "Disable BattlEye (commandline.txt)"
            )
        )
        self.nobattleye_toggle = ToggleSwitch()
        self.nobattleye_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Paths.Tooltip.NoBattlEye",
                "Adds or removes -nobattleye in commandline.txt inside your GTA V directory to run without BattlEye",
            )
        )
        self.nobattleye_toggle.toggled.connect(self._on_nobattleye_toggled)
        self.nobattleye_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.nobattleye_label, has_focus
            )
        )

        nobattleye_row.addWidget(self.nobattleye_label)
        nobattleye_row.addStretch()
        nobattleye_row.addWidget(self.nobattleye_toggle)

        layout.addSpacing(10)
        layout.addLayout(nobattleye_row)

        return frame

    def _on_nobattleye_toggled(self, checked: bool):
        """Called when the user toggles the -nobattleye switch."""
        gta_dir = process_manager.get_gta_directory(self.get_mode())
        if not gta_dir or not os.path.isdir(gta_dir):
            self.nobattleye_toggle.blockSignals(True)
            self.nobattleye_toggle.setChecked(False)
            self.nobattleye_toggle.blockSignals(False)

            self._notify(
                self.loc_manager.tr("Common.Error", "Error"),
                self.loc_manager.tr(
                    "Settings.Notify.NoGtaDirFound",
                    "Could not find your GTA V directory. Please browse and select your GTA V install folder first.",
                ),
                icon_type="error",
                duration=6000,
            )
            return

        success = process_manager.set_nobattleye_enabled(gta_dir, checked)
        if success:
            if checked:
                self._notify(
                    self.loc_manager.tr(
                        "Settings.Notify.BattlEyeDisabledTitle",
                        "BattlEye Disabled",
                    ),
                    self.loc_manager.tr(
                        "Settings.Notify.BattlEyeDisabledMsg",
                        "Added -nobattleye to commandline.txt in your GTA V directory.",
                    ),
                    icon_type="success",
                )
            else:
                self._notify(
                    self.loc_manager.tr(
                        "Settings.Notify.BattlEyeRestoredTitle",
                        "BattlEye Restored",
                    ),
                    self.loc_manager.tr(
                        "Settings.Notify.BattlEyeRestoredMsg",
                        "Removed -nobattleye from commandline.txt.",
                    ),
                    icon_type="info",
                )
        else:
            current_state = process_manager.is_nobattleye_enabled(gta_dir)
            self.nobattleye_toggle.blockSignals(True)
            self.nobattleye_toggle.setChecked(current_state)
            self.nobattleye_toggle.blockSignals(False)
            self._notify(
                self.loc_manager.tr("Common.Error", "Error"),
                self.loc_manager.tr(
                    "Settings.Paths.ErrorWriteCommandline",
                    "Could not modify commandline.txt. Please check file permissions.",
                ),
                icon_type="error",
            )

    def _update_nobattleye_toggle_state(self):
        """Refreshes the nobattleye toggle state from disk."""
        gta_dir = process_manager.get_gta_directory(self.get_mode())
        is_enabled = (
            process_manager.is_nobattleye_enabled(gta_dir) if gta_dir else False
        )
        self.nobattleye_toggle.blockSignals(True)
        self.nobattleye_toggle.setChecked(is_enabled)
        self.nobattleye_toggle.blockSignals(False)

    def _build_injection_frame(self) -> QFrame:
        """Builds the Injection preferences card."""
        frame = QFrame()
        frame.setObjectName("CardFrame")
        layout = QVBoxLayout(frame)

        title = QLabel(self.loc_manager.tr("Settings.Header.Injection", "Injection"))
        title.setObjectName("SettingsTitle")

        auto_close_row = QHBoxLayout()
        self.auto_close_label = QLabel(
            self.loc_manager.tr(
                "Settings.Inject.AutoClose", "Auto-Close after Injection"
            )
        )
        self.auto_close_toggle = ToggleSwitch()
        self.auto_close_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Inject.Tooltip.AutoClose",
                "Automatically close YMU once the DLL has been injected into the game",
            )
        )
        self.auto_close_toggle.setChecked(
            bool(get_config().get("inject.auto_close", False))
        )
        self.auto_close_toggle.toggled.connect(self._on_auto_close_toggled)
        self.auto_close_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.auto_close_label, has_focus
            )
        )

        auto_close_row.addWidget(self.auto_close_label)
        auto_close_row.addStretch()
        auto_close_row.addWidget(self.auto_close_toggle)

        sound_feedback_row = QHBoxLayout()
        self.sound_feedback_label = QLabel(
            self.loc_manager.tr(
                "Settings.Inject.SoundFeedback", "Sound Feedback on Success"
            )
        )
        self.sound_feedback_toggle = ToggleSwitch()
        self.sound_feedback_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Inject.Tooltip.SoundFeedback",
                "Play an audible confirmation chime when injection or download completes successfully",
            )
        )
        self.sound_feedback_toggle.setChecked(
            bool(get_config().get("inject.sound_feedback", True))
        )
        self.sound_feedback_toggle.toggled.connect(self._on_sound_feedback_toggled)
        self.sound_feedback_toggle.focusChanged.connect(
            lambda has_focus: self._on_toggle_focus_changed(
                self.sound_feedback_label, has_focus
            )
        )

        sound_feedback_row.addWidget(self.sound_feedback_label)
        sound_feedback_row.addStretch()
        sound_feedback_row.addWidget(self.sound_feedback_toggle)

        layout.addWidget(title)
        layout.addLayout(auto_close_row)
        layout.addLayout(sound_feedback_row)

        return frame

    def _on_auto_close_toggled(self, checked: bool):
        """Called when the user toggles the auto-close switch."""
        get_config().set("inject.auto_close", checked)

    def _on_sound_feedback_toggled(self, checked: bool):
        """Called when the user toggles the sound feedback switch."""
        get_config().set("inject.sound_feedback", checked)

    def _browse_gta_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self.loc_manager.tr("Settings.Paths.GtaDir", "GTA V install folder"),
        )
        if not directory:
            return
        if not os.path.isdir(directory):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNotFound", "Path does not exist."
                )
            )
            return
        gta_exes = ("playgtav.exe", "gta5.exe", "gta5_enhanced.exe")
        present = {f.lower() for f in os.listdir(directory)}
        if not present.intersection(gta_exes):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNoGta",
                    "No GTA V executable found in this folder.",
                )
            )
            return
        get_config().set("paths.gta_dir", directory)
        self.gta_dir_edit.setText(directory)
        self._update_nobattleye_toggle_state()

    def _browse_custom_dll(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.loc_manager.tr("Settings.Paths.CustomDll", "Custom menu DLL"),
            "",
            "DLL files (*.dll)",
        )
        if not file_path:
            return
        if not os.path.isfile(file_path) or not file_path.lower().endswith(".dll"):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNotDll", "Please select a .dll file."
                )
            )
            return
        get_config().set("paths.custom_dll", file_path)
        self.custom_dll_edit.setText(file_path)

    def _clear_path(self, key: str):
        get_config().set(key, None)
        if key == "paths.gta_dir":
            self.gta_dir_edit.clear()
            self._update_nobattleye_toggle_state()
        elif key == "paths.custom_dll":
            self.custom_dll_edit.clear()

    def _path_error(self, message: str):
        self._notify(
            self.loc_manager.tr("Common.Error", "Error"),
            message,
            icon_type="error",
        )

    def _open_link(self, path_or_url: str):
        """Opens a local folder path or a web URL."""
        if path_or_url.lower().startswith(("http://", "https://")):
            webbrowser.open(path_or_url)
        elif os.path.isdir(path_or_url):
            os.startfile(path_or_url)
        else:
            fmt = self.loc_manager.tr(
                "Settings.Notify.FolderMissing", "Folder does not exist yet:\n{0}"
            )
            self._notify(
                self.loc_manager.tr("Common.Info", "Information"),
                fmt.format(path_or_url),
                icon_type="info",
            )

    def _load_initial_settings(self):
        """Loads the active edition's YimMenu settings and sets the UI state.
        Signals are blocked so this never echoes writes back to the file."""
        settings_file = self.get_mode().settings_file

        is_enabled = settings_manager.get_setting(
            "lua.enable_auto_reload_changed_scripts",
            default=False,
            settings_file=settings_file,
        )
        self.auto_reload_toggle.blockSignals(True)
        self.auto_reload_toggle.setChecked(bool(is_enabled))
        self.auto_reload_toggle.blockSignals(False)

        is_debug_enabled = settings_manager.get_setting(
            "debug.external_console", default=False, settings_file=settings_file
        )
        self.debug_console_toggle.blockSignals(True)
        self.debug_console_toggle.setChecked(bool(is_debug_enabled))
        self.debug_console_toggle.blockSignals(False)

        self.auto_close_toggle.blockSignals(True)
        self.auto_close_toggle.setChecked(
            bool(get_config().get("inject.auto_close", False))
        )
        self.auto_close_toggle.blockSignals(False)

        self.sound_feedback_toggle.blockSignals(True)
        self.sound_feedback_toggle.setChecked(
            bool(get_config().get("inject.sound_feedback", True))
        )
        self.sound_feedback_toggle.blockSignals(False)

        self._update_nobattleye_toggle_state()

    def _write_yim_setting(self, key_path: str, value):
        """Writes into the active edition's settings.json. YimMenuV2's file is
        never created from scratch (unknown schema — YMU does not own it)."""
        mode = self.get_mode()
        ok = settings_manager.set_setting(
            key_path,
            value,
            settings_file=mode.settings_file,
            create_if_missing=(mode.key == "legacy"),
        )
        if not ok and mode.key != "legacy":
            msg = self.loc_manager.tr(
                "Settings.Notify.V2FileMissing",
                "YimMenuV2 has no settings.json yet.\nInject and run it once, then try again.",
            )
            self._notify(
                self.loc_manager.tr("Common.Info", "Information"),
                msg,
                icon_type="info",
            )

    def _on_auto_reload_toggled(self, checked: bool):
        """Called when the user clicks the auto-reload toggle."""
        self._write_yim_setting("lua.enable_auto_reload_changed_scripts", checked)

    def _on_debug_console_toggled(self, checked: bool):
        """Called when the user clicks the debug console toggle."""
        self._write_yim_setting("debug.external_console", checked)

    def _on_toggle_focus_changed(self, label: QLabel, has_focus: bool):
        """Updates the style of a label based on the focus state of its toggle."""
        if has_focus:
            if self.theme_manager.current_theme == "dark":
                label.setStyleSheet("text-decoration: underline; color: #FFFFFF;")
            else:
                label.setStyleSheet("text-decoration: underline; color: #000000;")
        else:
            label.setStyleSheet("")

    def _refresh_lua_lists(self):
        """Fetches the active edition's script lists, updates UI, and plays a
        brief feedback animation."""

        self.btn_refresh_luas.start_animation(duration=500)
        self.btn_refresh_luas.setEnabled(False)

        self.disabled_scripts_list.clear()
        self.enabled_scripts_list.clear()

        mode = self.get_mode()
        available = lua_manager.scripts_available(mode.appdata_dir)
        if not available:
            fmt = self.loc_manager.tr(
                "Settings.Lua.NoScriptsDir",
                "No {0} folder found yet.\nInject and run it once to create it.",
            )
            self.lua_hint_label.setText(fmt.format(mode.display_name))
        self.lua_hint_label.setVisible(not available)
        self.disabled_scripts_list.setEnabled(available)
        self.enabled_scripts_list.setEnabled(available)
        self.btn_enable_script.setEnabled(available)
        self.btn_disable_script.setEnabled(available)

        scripts = (
            lua_manager.get_scripts(mode.scripts_dir, mode.disabled_scripts_dir)
            if available
            else {"enabled": [], "disabled": []}
        )
        self.disabled_scripts_list.addItems(scripts["disabled"])
        self.enabled_scripts_list.addItems(scripts["enabled"])

        item_count = max(
            self.disabled_scripts_list.count(), self.enabled_scripts_list.count()
        )
        height = 100
        if item_count > 0:
            reference_list = (
                self.disabled_scripts_list
                if self.disabled_scripts_list.count() > 0
                else self.enabled_scripts_list
            )
            row_height = reference_list.sizeHintForRow(0)
            if row_height > 0:
                height = item_count * row_height + 10
        max_height = 200
        final_height = min(height, max_height)
        self.disabled_scripts_list.setFixedHeight(final_height)
        self.enabled_scripts_list.setFixedHeight(final_height)

        QTimer.singleShot(500, lambda: self.btn_refresh_luas.setEnabled(True))

    def _enable_selected_scripts(self):
        """Moves selected scripts from the disabled list to the enabled list."""
        selected_items = self.disabled_scripts_list.selectedItems()
        if not selected_items:
            return

        mode = self.get_mode()
        for item in selected_items:
            lua_manager.enable_script(
                mode.scripts_dir, mode.disabled_scripts_dir, item.text()
            )

        self._refresh_lua_lists()

    def _disable_selected_scripts(self):
        """Moves selected scripts from the enabled list to the disabled list."""
        selected_items = self.enabled_scripts_list.selectedItems()
        if not selected_items:
            return

        mode = self.get_mode()
        for item in selected_items:
            lua_manager.disable_script(
                mode.scripts_dir, mode.disabled_scripts_dir, item.text()
            )

        self._refresh_lua_lists()

    def _handle_check_for_updates(self):
        """Starts the background task to check for YMU updates."""
        if self._is_task_running:
            return

        self._is_task_running = True
        self.btn_check_for_updates.setEnabled(False)
        self.btn_check_for_updates.start_animation()

        self.worker_manager.run_exclusive(
            "ymu_update",
            update_checker.check_for_updates,
            on_finished=self._on_update_check_finished,
            on_error=self._on_task_error,
        )

    def _on_update_check_finished(self, result):
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.setEnabled(True)
        self._is_task_running = False

        status, data = result

        if status == update_checker.STATUS_UP_TO_DATE:
            self._notify(
                self.loc_manager.tr("Settings.Update.Title", "YMU Updater"),
                self.loc_manager.tr(
                    "Settings.Update.UpToDate", "Your YMU is already up-to-date."
                ),
                icon_type="success",
            )
            self.btn_check_for_updates.setText(
                self.loc_manager.tr("Settings.Btn.UpToDate", "YMU is up-to-date")
            )
            QTimer.singleShot(
                5000,
                lambda: self.btn_check_for_updates.setText(
                    self.loc_manager.tr(
                        "Settings.Btn.CheckUpdates", "Check for YMU Updates"
                    )
                ),
            )

        elif status == update_checker.STATUS_UPDATE_AVAILABLE:
            title = self.loc_manager.tr(
                "Settings.Update.AvailableTitle", "Update Available"
            )
            msg = self.loc_manager.tr(
                "Settings.Update.AvailableMsg", "Update {0} is available!"
            ).format(data)
            prompt = self.loc_manager.tr(
                "Settings.Update.Prompt",
                "Do you want to open the download page in your browser?",
            )

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(title)
            msg_box.setText(f"{msg}\n\n{prompt}")
            msg_box.setIcon(QMessageBox.Icon.Question)

            btn_yes = msg_box.addButton(
                self.loc_manager.tr("Common.Yes", "Yes"), QMessageBox.ButtonRole.YesRole
            )
            msg_box.addButton(
                self.loc_manager.tr("Common.No", "No"), QMessageBox.ButtonRole.NoRole
            )

            msg_box.exec()

            if msg_box.clickedButton() == btn_yes:
                webbrowser.open(update_checker.RELEASES_URL)

        elif status == update_checker.STATUS_AHEAD:
            self._notify(
                self.loc_manager.tr("Settings.Update.CheckTitle", "YMU Update Check"),
                self.loc_manager.tr(
                    "Settings.Update.Ahead", "You are running a newer version..."
                ),
                icon_type="info",
            )

        else:
            self._notify(
                self.loc_manager.tr("Settings.Update.ErrorTitle", "Update Error"),
                f"{self.loc_manager.tr('Common.Error')}: {data}",
                icon_type="error",
            )

    def _on_fetch_lang_clicked(self):
        """Start the manual download and animation."""
        self.btn_update_lang.setEnabled(False)
        self.btn_update_lang.start_animation(duration=500)
        self.loc_manager.fetch_updates()

    def _on_lang_fetch_finished(
        self, success: bool, message: str, restart_needed: bool
    ):
        """Callback from the manager."""
        self.btn_update_lang.stop_animation()
        self.btn_update_lang.setEnabled(True)
        if success:
            title = self.loc_manager.tr("Common.Info", "Information")
            if restart_needed:
                msg = self.loc_manager.tr(
                    "Settings.Notify.LangUpdated",
                    "Translations were successfully downloaded.\nRestart YMU to see the updated Language List in Settings.",
                )
                action_text = self.loc_manager.tr("Common.Restart", "Restart Now")
                self._notify(
                    title,
                    msg,
                    icon_type="success",
                    duration=10000,
                    action_text=action_text,
                    action_callback=restart_application,
                )
            else:
                self._notify(
                    title, message, icon_type="success"
                )
        else:
            self._notify(
                self.loc_manager.tr("Common.Error", "Error"), message, icon_type="error"
            )

    def _commit_language_change(self):
        index = self.lang_combo.currentIndex()
        if index < 0:
            return
        new_locale_code = self.lang_combo.itemData(index)

        if new_locale_code == self.loc_manager.active_locale:
            return

        self.loc_manager.set_locale(new_locale_code)

        msg = self.loc_manager.tr(
            "Settings.Notify.RestartRequired",
            "Please restart YMU to apply the new language.",
        )

        title = self.loc_manager.tr("Settings.Notify.LangTitle", "Language Changed")
        action = self.loc_manager.tr("Common.Restart", "Restart Now")

        self._notify(
            title,
            msg,
            icon_type="info",
            duration=10000,
            action_text=action,
            action_callback=restart_application,
            tag="language_change",
        )

    def _on_task_error(self, error: Exception):
        """A generic callback to handle any errors from the worker tasks."""
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.reset_progress()
        self.btn_check_for_updates.setText(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates")
        )
        self.btn_check_for_updates.setEnabled(True)
        self._is_task_running = False

        logger.error(f"A settings page task failed in the background: {error}")
        self._notify(
            self.loc_manager.tr("Common.Error", "Error"),
            f"{self.loc_manager.tr('Common.UnexpectedError', 'An unexpected error occurred')}: {error}",
            icon_type="error",
        )
