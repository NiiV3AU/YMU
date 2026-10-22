# settings_page.py - Settings UI for theme, language, lua scripts, paths, and updates.
import contextlib
import logging
import os
import webbrowser
from itertools import pairwise
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QSize, Qt, QTimer, Slot
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core import lua_manager, process_manager, update_checker
from core import settings as settings_manager
from core.config import get_config
from core.maintenance import (
    FslStatus,
    bulk_toggle_scripts,
    clear_menu_caches,
    get_fsl_status,
)
from core.menu_modes import MenuMode
from core.paths import YMU_APPDATA_DIR, resource_path
from ui.utils import (
    adjust_combobox_to_contents,
    create_colored_icon,
    restart_application,
    restart_as_admin,
)
from ui.widgets.buttons import AnimatedButton, StatefulButton
from ui.widgets.dialogs import AboutDialog
from ui.widgets.lua_item import LuaScriptItemWidget
from ui.widgets.notifications import NotificationManager
from ui.widgets.path_line_edit import PathLineEdit
from ui.widgets.toggle_switch import ToggleSwitch

if TYPE_CHECKING:
    from core.worker_manager import WorkerManager
    from ui.i18n.localization_manager import LocalizationManager
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

# Geometry of the two script lists. The visible height tracks the larger of the
# two script counts, clamped to a range that keeps the panel from collapsing or
# growing without bound.
LUA_ROW_HEIGHT = 30
LUA_LIST_FRAME_OVERHEAD = 6
LUA_LIST_MIN_ROWS = 3
LUA_LIST_MAX_ROWS = 7


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
        self._mode = None
        self._cached_gta_dir: dict[str, str | None] = {}

        scroll_content_widget = QWidget()
        scroll_content_widget.setObjectName("ScrollContainer")
        content_layout = QVBoxLayout(scroll_content_widget)
        content_layout.setContentsMargins(16, 20, 16, 20)
        content_layout.setSpacing(16)

        self.appearance_frame = QFrame()
        self.appearance_frame.setObjectName("CardFrame")
        appearance_layout = QVBoxLayout(self.appearance_frame)

        appearance_title = QLabel(
            self.loc_manager.tr("Settings.Header.Appearance", "Appearance")
        )
        appearance_title.setObjectName("SettingsTitle")

        theme_button_layout = QHBoxLayout()
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)

        self.btn_dark_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Dark', 'Dark')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "moon.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        self.btn_dark_theme.setObjectName("ThemeButton")
        self.btn_dark_theme.setCheckable(True)

        self.btn_light_theme = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Theme.Light', 'Light')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "sun.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#CCCCCC", "#121212"),
            color_checked=("#121212", "#FFFFFF"),
        )
        self.btn_light_theme.setObjectName("ThemeButton")
        self.btn_light_theme.setCheckable(True)

        self.theme_group.addButton(self.btn_dark_theme)
        self.theme_group.addButton(self.btn_light_theme)

        if self.theme_manager.current_theme == "light":
            self.btn_light_theme.setChecked(True)
        else:
            self.btn_dark_theme.setChecked(True)

        self.theme_group.buttonClicked.connect(self._on_theme_button_clicked)
        self.btn_dark_theme.clicked.connect(self._apply_dark_theme)
        self.btn_light_theme.clicked.connect(self._apply_light_theme)

        theme_button_layout.addWidget(self.btn_dark_theme)
        theme_button_layout.addWidget(self.btn_light_theme)

        lang_layout = QHBoxLayout()
        lang_label = QLabel(self.loc_manager.tr("Settings.Label.Language", "Language"))

        self.lang_combo = QComboBox()
        self.lang_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lang_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.lang_combo.view().setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        if isinstance(lang_view := self.lang_combo.view(), QListView):
            lang_view.setUniformItemSizes(True)
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

        adjust_combobox_to_contents(self.lang_combo, min_width=160)

        self._lang_debounce_timer = QTimer(self)
        self._lang_debounce_timer.setSingleShot(True)
        self._lang_debounce_timer.setInterval(250)
        self._lang_debounce_timer.timeout.connect(self._commit_language_change)

        self.btn_update_lang = AnimatedButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "cloud-download.svg")
            ),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.btn_update_lang.setObjectName("RefreshButton")
        self.btn_update_lang.setFixedSize(44, 44)
        self.btn_update_lang.setIconSize(QSize(20, 20))
        self.btn_update_lang.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.UpdateLang", "Check for translation updates"
            )
        )

        self.btn_update_lang.clicked.connect(self._on_fetch_lang_clicked)
        self.loc_manager.update_finished.connect(self._on_lang_fetch_finished)
        self.lang_combo.currentIndexChanged.connect(self._on_language_index_changed)
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
        self.lua_frame = QFrame()
        self.lua_frame.setObjectName("CardFrame")
        lua_layout = QVBoxLayout(self.lua_frame)

        lua_title = QLabel(self.loc_manager.tr("Settings.Header.Lua", "Lua Settings"))
        lua_title.setObjectName("SettingsTitle")

        auto_reload_layout = QHBoxLayout()
        self.auto_reload_label = QLabel(
            self.loc_manager.tr(
                "Settings.Lua.AutoReload", "Auto-reload changed scripts"
            )
        )
        self.auto_reload_label.setWordWrap(True)
        self.auto_reload_toggle = ToggleSwitch(theme_manager=self.theme_manager)
        self.auto_reload_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.AutoReload",
                "Automatically re-apply changes when Lua script files are saved",
            )
        )
        self.auto_reload_label.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.AutoReload",
                "Automatically re-apply changes when Lua script files are saved",
            )
        )

        auto_reload_layout.addWidget(self.auto_reload_label, stretch=1)
        auto_reload_layout.addWidget(self.auto_reload_toggle)

        lua_layout.addWidget(lua_title)
        lua_layout.addLayout(auto_reload_layout)

        self.lua_hint_label = QLabel("")
        self.lua_hint_label.setObjectName("RiskInfoLabel")
        self.lua_hint_label.setWordWrap(True)
        self.lua_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lua_hint_label.setVisible(False)
        lua_layout.addWidget(self.lua_hint_label)

        # Lists container (Disabled column | Enabled column)
        lists_container_layout = QHBoxLayout()
        lists_container_layout.setSpacing(16)

        # 1. Disabled Scripts Column
        disabled_col_layout = QVBoxLayout()
        disabled_col_layout.setSpacing(8)

        disabled_header_layout = QHBoxLayout()
        disabled_header_layout.setContentsMargins(0, 0, 0, 0)
        self.disabled_header_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListDisabled", "Disabled")
        )
        self.disabled_header_label.setObjectName("DisabledListHeader")

        self.btn_enable_all_scripts = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "circle-check.svg")
            ),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#28A745", "#28A745"),
        )
        self.btn_enable_all_scripts.setObjectName("LuaHeaderAction")
        self.btn_enable_all_scripts.setIconSize(QSize(14, 14))
        self.btn_enable_all_scripts.setFixedSize(26, 26)
        self.btn_enable_all_scripts.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.btn_enable_all_scripts.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.EnableAll",
                "Re-enable all disabled scripts",
            )
        )
        self.btn_enable_all_scripts.clicked.connect(self._on_enable_all_scripts_clicked)

        disabled_header_layout.addWidget(self.disabled_header_label)
        disabled_header_layout.addStretch()
        disabled_header_layout.addWidget(
            self.btn_enable_all_scripts, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self.disabled_scripts_list = QListWidget()
        self.disabled_scripts_list.setFixedHeight(96)
        self.disabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.disabled_scripts_list.installEventFilter(self)
        self.disabled_scripts_list.itemDoubleClicked.connect(
            self._on_disabled_item_double_clicked
        )

        disabled_col_layout.addLayout(disabled_header_layout)
        disabled_col_layout.addWidget(self.disabled_scripts_list)

        # 2. Enabled Scripts Column
        enabled_col_layout = QVBoxLayout()
        enabled_col_layout.setSpacing(8)

        enabled_header_layout = QHBoxLayout()
        enabled_header_layout.setContentsMargins(0, 0, 0, 0)
        self.enabled_header_label = QLabel(
            self.loc_manager.tr("Settings.Lua.ListEnabled", "Enabled")
        )
        self.enabled_header_label.setObjectName("EnabledListHeader")

        self.btn_disable_all_scripts = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "x.svg")),
            color_normal=("#8B8B8B", "#555555"),
            color_hover=("#e84555", "#e84555"),
        )
        self.btn_disable_all_scripts.setObjectName("LuaHeaderAction")
        self.btn_disable_all_scripts.setIconSize(QSize(14, 14))
        self.btn_disable_all_scripts.setFixedSize(26, 26)
        self.btn_disable_all_scripts.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.btn_disable_all_scripts.setToolTip(
            self.loc_manager.tr(
                "Settings.Lua.Tooltip.DisableAll",
                "Disable all scripts at once (Safe Mode)",
            )
        )
        self.btn_disable_all_scripts.clicked.connect(
            self._on_disable_all_scripts_clicked
        )

        enabled_header_layout.addWidget(self.enabled_header_label)
        enabled_header_layout.addStretch()
        enabled_header_layout.addWidget(
            self.btn_disable_all_scripts, alignment=Qt.AlignmentFlag.AlignVCenter
        )

        self.enabled_scripts_list = QListWidget()
        self.enabled_scripts_list.setFixedHeight(96)
        self.enabled_scripts_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.enabled_scripts_list.installEventFilter(self)
        self.enabled_scripts_list.itemDoubleClicked.connect(
            self._on_enabled_item_double_clicked
        )

        enabled_col_layout.addLayout(enabled_header_layout)
        enabled_col_layout.addWidget(self.enabled_scripts_list)

        lists_container_layout.addLayout(disabled_col_layout, stretch=1)
        lists_container_layout.addLayout(enabled_col_layout, stretch=1)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }
        footer_layout = QHBoxLayout()
        self.btn_open_scripts_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenScripts', 'Open Scripts Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder-open.svg")),
            **link_button_colors,
        )
        self.btn_open_scripts_folder.setObjectName("LinkButton")
        self.btn_open_scripts_folder.setIconSize(QSize(20, 20))
        self.btn_open_scripts_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenScripts",
                "Open the folder where your Lua scripts are located",
            )
        )

        self.btn_discover_luas = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.DiscoverLua', 'Discover Luas')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        self.btn_discover_luas.setObjectName("LinkButton")
        self.btn_discover_luas.setIconSize(QSize(20, 20))
        self.btn_discover_luas.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.DiscoverLua",
                "Open the official YimMenu-Lua GitHub organization to find new scripts",
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
        self.btn_refresh_luas.setFixedSize(44, 44)
        self.btn_refresh_luas.setToolTip(
            self.loc_manager.tr("Settings.Lua.Tooltip.Refresh", "Refresh script lists")
        )

        footer_layout.addWidget(self.btn_open_scripts_folder)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_refresh_luas)
        footer_layout.addStretch()
        footer_layout.addWidget(self.btn_discover_luas)

        lua_layout.addSpacing(12)
        lua_layout.addLayout(lists_container_layout)
        lua_layout.addSpacing(10)
        lua_layout.addLayout(footer_layout)

        self.other_frame = QFrame()
        self.other_frame.setObjectName("CardFrame")
        other_layout = QVBoxLayout(self.other_frame)

        other_title = QLabel(self.loc_manager.tr("Settings.Header.Other", "Other"))
        other_title.setObjectName("SettingsTitle")

        debug_console_layout = QHBoxLayout()
        self.debug_console_label = QLabel(
            self.loc_manager.tr(
                "Settings.Other.DebugConsole", "Enable External Debug Console"
            )
        )
        self.debug_console_label.setWordWrap(True)
        self.debug_console_toggle = ToggleSwitch(theme_manager=self.theme_manager)
        self.debug_console_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Other.Tooltip.Debug",
                "Show YimMenu's external console window for detailed logs and debugging",
            )
        )
        debug_console_layout.addWidget(self.debug_console_label, stretch=1)
        debug_console_layout.addWidget(self.debug_console_toggle)

        self.btn_open_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYimFolder', 'Open YimMenu Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder-open.svg")),
            **link_button_colors,
        )
        self.btn_open_folder.setObjectName("LinkButton")
        self.btn_open_folder.setIconSize(QSize(20, 20))
        self.btn_open_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYimFolder",
                "Open YimMenu folder (%APPDATA%/YimMenu)",
            )
        )

        self.btn_open_ymu_folder = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenYmuFolder', 'Open YMU Folder')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "folder-open.svg")),
            **link_button_colors,
        )
        self.btn_open_ymu_folder.setObjectName("LinkButton")
        self.btn_open_ymu_folder.setIconSize(QSize(20, 20))
        self.btn_open_ymu_folder.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenYmuFolder", "Open YMU folder (%APPDATA%/YMU)"
            )
        )

        self.btn_report_bug = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.ReportBug', 'Report a Bug')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        self.btn_report_bug.setObjectName("LinkButton")
        self.btn_report_bug.setIconSize(QSize(20, 20))
        self.btn_report_bug.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.ReportBug",
                "Open the bug report page on GitHub in your browser",
            )
        )

        self.btn_request_feature = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.RequestFeature', 'Request a Feature')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        self.btn_request_feature.setObjectName("LinkButton")
        self.btn_request_feature.setIconSize(QSize(20, 20))
        self.btn_request_feature.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.RequestFeature",
                "Open the feature request page on GitHub in your browser",
            )
        )
        self.btn_check_for_updates = AnimatedButton(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates"),
            theme_manager=self.theme_manager,
        )
        self.btn_about = StatefulButton(
            f"  {self.loc_manager.tr('About.BtnLabel', 'About YMU')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "info.svg")),
            **link_button_colors,
        )
        self.btn_about.setObjectName("LinkButton")
        self.btn_about.setIconSize(QSize(20, 20))
        self.btn_about.setToolTip(
            self.loc_manager.tr(
                "About.Tooltip",
                "View project information, dependencies, and open-source licenses",
            )
        )
        other_layout.addWidget(other_title)
        other_layout.addLayout(debug_console_layout)
        other_layout.addSpacing(4)

        other_buttons_grid = QGridLayout()
        other_buttons_grid.setHorizontalSpacing(10)
        other_buttons_grid.setVerticalSpacing(8)
        other_buttons_grid.addWidget(self.btn_open_folder, 0, 0)
        other_buttons_grid.addWidget(self.btn_open_ymu_folder, 0, 1)
        other_buttons_grid.addWidget(self.btn_report_bug, 1, 0)
        other_buttons_grid.addWidget(self.btn_request_feature, 1, 1)
        other_layout.addLayout(other_buttons_grid)

        other_layout.addSpacing(16)
        other_layout.addWidget(
            self.btn_check_for_updates, alignment=Qt.AlignmentFlag.AlignCenter
        )
        other_layout.addSpacing(6)
        other_layout.addWidget(self.btn_about, alignment=Qt.AlignmentFlag.AlignCenter)

        self.paths_frame = self._build_paths_frame()
        self.injection_frame = self._build_injection_frame()
        self.maintenance_frame = self._build_maintenance_frame()

        content_layout.addWidget(self.appearance_frame)
        content_layout.addWidget(self.lua_frame)
        content_layout.addWidget(self.paths_frame)
        content_layout.addWidget(self.injection_frame)
        content_layout.addWidget(self.maintenance_frame)
        content_layout.addWidget(self.other_frame)
        content_layout.addStretch()

        self.scroll_area = QScrollArea()
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(scroll_content_widget)

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.scroll_area)

        self.btn_open_folder.clicked.connect(self._on_open_appdata_clicked)
        self.btn_open_ymu_folder.clicked.connect(self._on_open_ymu_appdata_clicked)

        self.btn_report_bug.clicked.connect(self._on_report_bug_clicked)
        self.btn_request_feature.clicked.connect(self._on_request_feature_clicked)
        self.btn_check_for_updates.clicked.connect(self._handle_check_for_updates)
        self.btn_about.clicked.connect(self._show_about_dialog)
        self.auto_reload_toggle.toggled.connect(self._on_auto_reload_toggled)
        self.debug_console_toggle.toggled.connect(self._on_debug_console_toggled)
        self.auto_reload_toggle.focusChanged.connect(self._on_any_toggle_focus_changed)
        self.debug_console_toggle.focusChanged.connect(
            self._on_any_toggle_focus_changed
        )
        self.btn_open_scripts_folder.clicked.connect(
            self._on_open_scripts_folder_clicked
        )
        self.btn_refresh_luas.clicked.connect(self._refresh_lua_lists)
        self.btn_discover_luas.clicked.connect(self._on_discover_luas_clicked)

        # Unified keyboard tab chain connecting all frames in visual reading order
        tab_chain = [
            self.btn_dark_theme,
            self.btn_light_theme,
            self.btn_update_lang,
            self.lang_combo,
            self.auto_reload_toggle,
            self.btn_enable_all_scripts,
            self.disabled_scripts_list,
            self.btn_disable_all_scripts,
            self.enabled_scripts_list,
            self.btn_open_scripts_folder,
            self.btn_refresh_luas,
            self.btn_discover_luas,
            self.gta_dir_edit,
            self.btn_browse_gta,
            self.btn_clear_gta,
            self.custom_dll_edit,
            self.btn_browse_dll,
            self.btn_clear_dll,
            self.nobattleye_toggle,
            self.btn_fsl_help,
            self.auto_close_toggle,
            self.sound_feedback_toggle,
            self.btn_reset_caches,
            self.btn_open_log,
            self.debug_console_toggle,
            self.btn_open_folder,
            self.btn_open_ymu_folder,
            self.btn_report_bug,
            self.btn_request_feature,
            self.btn_check_for_updates,
            self.btn_about,
        ]
        for first, second in pairwise(tab_chain):
            self.setTabOrder(first, second)

        self._refresh_lua_lists()
        self._load_initial_settings()

    @Slot(object)
    def on_mode_changed(self, mode: MenuMode):
        """Slot: the sidebar switch changed the active edition."""
        self._mode = mode
        self._cached_gta_dir.clear()
        self._refresh_lua_lists()
        self._load_initial_settings()

    @Slot()
    def _show_about_dialog(self):
        """Opens the modal About and Open Source Licenses dialog."""
        dialog = AboutDialog(
            theme_manager=self.theme_manager,
            loc_manager=self.loc_manager,
            parent=self,
        )
        dialog.exec()

    def _notify(self, title: str, message: str, **kwargs):
        win = self.window()
        mgr = getattr(win, "notification_manager", None)
        if isinstance(mgr, NotificationManager):
            mgr.show(title, message, **kwargs)

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
        self.gta_dir_edit = PathLineEdit(
            theme_manager=self.theme_manager,
            loc_manager=self.loc_manager,
        )
        self.gta_dir_edit.setPlaceholderText(
            self.loc_manager.tr("Settings.Paths.AutoDetect", "Auto-detected")
        )
        self.gta_dir_edit.setText(config.get("paths.gta_dir") or "")
        self.gta_dir_edit.editingFinished.connect(self._on_gta_dir_editing_finished)

        self.btn_browse_gta = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Browse', 'Browse')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "folder-search.svg")
            ),
            **link_button_colors,
        )
        self.btn_browse_gta.setObjectName("LinkButton")
        self.btn_clear_gta = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Clear', 'Clear')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "eraser.svg")),
            **link_button_colors,
        )
        self.btn_clear_gta.setObjectName("LinkButton")
        self.btn_browse_gta.clicked.connect(self._browse_gta_dir)
        self.btn_clear_gta.clicked.connect(self._on_clear_gta_clicked)

        gta_row = QHBoxLayout()
        gta_row.addWidget(self.gta_dir_edit, stretch=1)
        gta_row.addWidget(self.btn_browse_gta)
        gta_row.addWidget(self.btn_clear_gta)

        layout.addWidget(gta_label)
        layout.addLayout(gta_row)

        # --- Custom DLL row ---
        dll_label = QLabel(
            self.loc_manager.tr("Settings.Paths.CustomDll", "Custom menu DLL")
        )
        self.custom_dll_edit = PathLineEdit(
            theme_manager=self.theme_manager,
            loc_manager=self.loc_manager,
            browse_icon="file-search.svg",
        )
        self.custom_dll_edit.setPlaceholderText(
            self.loc_manager.tr("Settings.Paths.DefaultDll", "Use downloaded DLL")
        )
        self.custom_dll_edit.setText(config.get("paths.custom_dll") or "")
        self.custom_dll_edit.editingFinished.connect(
            self._on_custom_dll_editing_finished
        )

        self.btn_browse_dll = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Browse', 'Browse')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "file-search.svg")),
            **link_button_colors,
        )
        self.btn_browse_dll.setObjectName("LinkButton")
        self.btn_clear_dll = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.Clear', 'Clear')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "eraser.svg")),
            **link_button_colors,
        )
        self.btn_clear_dll.setObjectName("LinkButton")
        self.btn_browse_dll.clicked.connect(self._browse_custom_dll)
        self.btn_clear_dll.clicked.connect(self._on_clear_dll_clicked)

        dll_row = QHBoxLayout()
        dll_row.addWidget(self.custom_dll_edit, stretch=1)
        dll_row.addWidget(self.btn_browse_dll)
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
        self.nobattleye_label.setWordWrap(True)
        self.nobattleye_toggle = ToggleSwitch(theme_manager=self.theme_manager)
        self.nobattleye_toggle.setToolTip(
            self.loc_manager.tr(
                "Settings.Paths.Tooltip.NoBattlEye",
                "Adds or removes -nobattleye in commandline.txt inside your GTA V directory to run without BattlEye",
            )
        )
        self.nobattleye_toggle.toggled.connect(self._on_nobattleye_toggled)
        self.nobattleye_toggle.focusChanged.connect(self._on_any_toggle_focus_changed)

        nobattleye_row.addWidget(self.nobattleye_label, stretch=1)
        nobattleye_row.addWidget(self.nobattleye_toggle)

        # --- FSL (WINMM.dll) status row ---
        fsl_status_row = QHBoxLayout()
        fsl_status_row.setSpacing(6)
        self.fsl_status_icon = QLabel()
        self.fsl_status_icon.setFixedSize(16, 16)
        self.fsl_status_icon.hide()
        self.fsl_status_label = QLabel()
        self.fsl_status_label.setWordWrap(True)
        is_rtl = getattr(self.theme_manager, "is_rtl", False) or (
            self.loc_manager is not None and self.loc_manager.is_rtl()
        )
        fsl_icon = "arrow-left.svg" if is_rtl else "arrow-right.svg"
        self.btn_fsl_help = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Paths.FslHelp', 'FSL Info')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", fsl_icon)),
            **link_button_colors,
        )
        self.btn_fsl_help.setObjectName("LinkButton")
        self.btn_fsl_help.setIconSize(QSize(20, 20))
        self.btn_fsl_help.setToolTip(
            self.loc_manager.tr(
                "Settings.Paths.Tooltip.Fsl",
                "View important FSL information and download link on the Risks page",
            )
        )
        self.btn_fsl_help.clicked.connect(self._open_risks_page)
        fsl_status_row.addWidget(
            self.fsl_status_icon, alignment=Qt.AlignmentFlag.AlignVCenter
        )
        fsl_status_row.addWidget(
            self.fsl_status_label,
            stretch=1,
            alignment=Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addSpacing(10)
        layout.addLayout(nobattleye_row)
        layout.addSpacing(8)
        layout.addLayout(fsl_status_row)
        layout.addSpacing(4)
        layout.addWidget(self.btn_fsl_help, alignment=Qt.AlignmentFlag.AlignLeft)

        return frame

    @staticmethod
    def _run_nobattleye_toggle(
        mode_key: str, checked: bool, gta_dir: str
    ) -> tuple[str, bool, str, bool]:
        success = process_manager.set_nobattleye_enabled(gta_dir, checked)
        return (mode_key, checked, gta_dir, success)

    @Slot(bool)
    def _on_nobattleye_toggled(self, checked: bool):
        """Called when the user toggles the -nobattleye switch."""
        mode_val = self.get_mode()
        mode_key = getattr(mode_val, "key", str(mode_val))
        gta_dir = self._cached_gta_dir.get(mode_key)
        if not gta_dir:
            gta_dir = process_manager.get_gta_directory(mode_val)
            if gta_dir:
                self._cached_gta_dir[mode_key] = gta_dir
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

        self.nobattleye_toggle.setEnabled(False)
        self._nobattleye_toggle_ctx = (mode_key, gta_dir)

        started = self.worker_manager.run_exclusive(
            f"nobattleye_toggle_{mode_key}",
            self._run_nobattleye_toggle,
            mode_key,
            checked,
            gta_dir,
            on_finished=self._on_nobattleye_toggle_finished,
            on_error=self._on_nobattleye_toggle_error,
        )
        if not started:
            self.nobattleye_toggle.setEnabled(True)

    @Slot(object)
    def _on_nobattleye_toggle_finished(
        self, result: tuple[str, bool, str, bool]
    ) -> None:
        mode_key, checked, gta_dir, success = result
        self.nobattleye_toggle.setEnabled(True)
        curr_mode = self.get_mode()
        curr_key = getattr(curr_mode, "key", str(curr_mode))
        if curr_key != mode_key:
            return
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
            action_text = None
            action_cb = None
            if not process_manager.is_admin():
                action_text = self.loc_manager.tr(
                    "Common.RestartAdmin", "Restart as Admin"
                )
                action_cb = restart_as_admin

            self._notify(
                self.loc_manager.tr("Common.Error", "Error"),
                self.loc_manager.tr(
                    "Settings.Paths.ErrorWriteCommandline",
                    "Could not modify commandline.txt. Please check file permissions or run as Administrator.",
                ),
                icon_type="error",
                duration=8000 if action_text else 5000,
                action_text=action_text,
                action_callback=action_cb,
            )

    @Slot(Exception)
    def _on_nobattleye_toggle_error(self, exc: Exception) -> None:
        self.nobattleye_toggle.setEnabled(True)
        if not hasattr(self, "_nobattleye_toggle_ctx"):
            return
        mode_key, gta_dir = self._nobattleye_toggle_ctx
        curr_mode = self.get_mode()
        curr_key = getattr(curr_mode, "key", str(curr_mode))
        if curr_key != mode_key:
            return
        current_state = process_manager.is_nobattleye_enabled(gta_dir)
        self.nobattleye_toggle.blockSignals(True)
        self.nobattleye_toggle.setChecked(current_state)
        self.nobattleye_toggle.blockSignals(False)
        self._notify(
            self.loc_manager.tr("Common.Error", "Error"),
            str(exc),
            icon_type="error",
        )

    @staticmethod
    def _fetch_nobattleye_state(
        mode_key: str, mode_val: MenuMode, cached: str | None
    ) -> tuple[str, str | None, bool, FslStatus]:
        gta_dir = (
            cached
            if cached is not None
            else process_manager.get_gta_directory(mode_val)
        )
        is_enabled = (
            process_manager.is_nobattleye_enabled(gta_dir) if gta_dir else False
        )
        status = get_fsl_status(gta_dir)
        return mode_key, gta_dir, is_enabled, status

    def _update_nobattleye_toggle_state(self):
        """Refreshes the nobattleye toggle state and FSL status asynchronously via a background worker."""
        mode_val = self.get_mode()
        mode_key = getattr(mode_val, "key", str(mode_val))
        cached = self._cached_gta_dir.get(mode_key)

        self.worker_manager.run_exclusive(
            f"nobattleye_check_{mode_key}",
            self._fetch_nobattleye_state,
            mode_key,
            mode_val,
            cached,
            on_finished=self._on_nobattleye_check_finished,
            on_error=self._on_task_error,
        )

    @Slot(object)
    def _on_nobattleye_check_finished(
        self, result: tuple[str, str | None, bool, FslStatus]
    ) -> None:
        mode_key, gta_dir, is_enabled, status = result
        if gta_dir:
            self._cached_gta_dir[mode_key] = gta_dir
        else:
            self._cached_gta_dir.pop(mode_key, None)
        curr_mode = self.get_mode()
        curr_key = getattr(curr_mode, "key", str(curr_mode))
        if curr_key == mode_key:
            if hasattr(self, "nobattleye_toggle"):
                self.nobattleye_toggle.blockSignals(True)
                self.nobattleye_toggle.setChecked(is_enabled)
                self.nobattleye_toggle.blockSignals(False)
            self._apply_fsl_status(status)

    def _apply_fsl_status(self, status: FslStatus):
        """Updates the FSL detection status icon, label, and tooltip according to status."""
        if not hasattr(self, "fsl_status_label"):
            return
        if status == FslStatus.DETECTED:
            icon = create_colored_icon(
                resource_path(os.path.join("assets", "icons", "circle-check.svg")),
                QColor("#4CAF50"),
            )
            self.fsl_status_icon.setPixmap(icon.pixmap(16, 16))
            self.fsl_status_icon.setVisible(True)
            self.fsl_status_icon.setToolTip("")
            self.fsl_status_label.setText(
                self.loc_manager.tr(
                    "Settings.Paths.FslDetected", "FSL (WINMM.dll): Detected"
                )
            )
            self.fsl_status_label.setStyleSheet("color: #4CAF50; font-size: 14px;")
            self.fsl_status_label.setToolTip("")
        elif status == FslStatus.DEPRECATED:
            icon = create_colored_icon(
                resource_path(os.path.join("assets", "icons", "triangle-alert.svg")),
                QColor("#E6A23C"),
            )
            deprecated_tooltip = self.loc_manager.tr(
                "Settings.Paths.Tooltip.FslDeprecated",
                "Outdated version.dll found! This legacy file causes game crashes. Please delete it and install WINMM.dll from the FSL thread.",
            )
            self.fsl_status_icon.setPixmap(icon.pixmap(16, 16))
            self.fsl_status_icon.setVisible(True)
            self.fsl_status_icon.setToolTip(deprecated_tooltip)
            self.fsl_status_label.setText(
                self.loc_manager.tr(
                    "Settings.Paths.FslDeprecated",
                    "FSL (version.dll): Outdated (Crash risk)",
                )
            )
            self.fsl_status_label.setStyleSheet(
                "color: #E6A23C; font-size: 14px; font-weight: 500;"
            )
            self.fsl_status_label.setToolTip(deprecated_tooltip)
        else:
            self.fsl_status_icon.clear()
            self.fsl_status_icon.setVisible(False)
            self.fsl_status_icon.setToolTip("")
            self.fsl_status_label.setText(
                self.loc_manager.tr(
                    "Settings.Paths.FslMissing",
                    "FSL (WINMM.dll): Not found (Recommended for online)",
                )
            )
            self.fsl_status_label.setStyleSheet("color: #8B8B8B; font-size: 14px;")
            self.fsl_status_label.setToolTip("")

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
        self.auto_close_label.setWordWrap(True)
        self.auto_close_toggle = ToggleSwitch(theme_manager=self.theme_manager)
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
        self.auto_close_toggle.focusChanged.connect(self._on_any_toggle_focus_changed)

        auto_close_row.addWidget(self.auto_close_label, stretch=1)
        auto_close_row.addWidget(self.auto_close_toggle)

        sound_feedback_row = QHBoxLayout()
        self.sound_feedback_label = QLabel(
            self.loc_manager.tr(
                "Settings.Inject.SoundFeedback", "Sound Feedback on Success"
            )
        )
        self.sound_feedback_label.setWordWrap(True)
        self.sound_feedback_toggle = ToggleSwitch(theme_manager=self.theme_manager)
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
            self._on_any_toggle_focus_changed
        )

        sound_feedback_row.addWidget(self.sound_feedback_label, stretch=1)
        sound_feedback_row.addWidget(self.sound_feedback_toggle)

        layout.addWidget(title)
        layout.addLayout(auto_close_row)
        layout.addLayout(sound_feedback_row)

        return frame

    def _build_maintenance_frame(self) -> QFrame:
        """Builds the Maintenance card (cache reset, log viewer)."""
        frame = QFrame()
        frame.setObjectName("CardFrame")
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)

        title = QLabel(
            self.loc_manager.tr("Settings.Header.Maintenance", "Maintenance")
        )
        title.setObjectName("SettingsTitle")
        layout.addWidget(title)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }

        self.btn_reset_caches = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.ResetCaches', 'Clear Pointer Caches')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "database-zap.svg")
            ),
            **link_button_colors,
        )
        self.btn_reset_caches.setObjectName("LinkButton")
        self.btn_reset_caches.setIconSize(QSize(20, 20))
        self.btn_reset_caches.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.ResetCaches",
                "Deletes cached binary offsets. Recommended after game updates if the menu crashes on launch.",
            )
        )
        self.btn_reset_caches.clicked.connect(self._on_reset_caches_clicked)

        self.btn_open_log = StatefulButton(
            f"  {self.loc_manager.tr('Settings.Btn.OpenLog', 'Open YimMenu Log')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "file-text.svg")),
            **link_button_colors,
        )
        self.btn_open_log.setObjectName("LinkButton")
        self.btn_open_log.setIconSize(QSize(20, 20))
        self.btn_open_log.setToolTip(
            self.loc_manager.tr(
                "Settings.Tooltip.OpenLog",
                "Open the active edition's cout.log in your text editor",
            )
        )
        self.btn_open_log.clicked.connect(self._on_open_log_clicked)

        layout.addWidget(self.btn_reset_caches)
        layout.addWidget(self.btn_open_log)

        return frame

    def _update_lua_button_icons(self, _direction: object | None = None):
        """Refreshes Lua script lists to update transfer caret icons on layout direction changes."""
        self._refresh_lua_lists()

    def changeEvent(self, event: QEvent):
        super().changeEvent(event)
        if event.type() == QEvent.Type.LayoutDirectionChange:
            self._update_lua_button_icons()

    @staticmethod
    def _run_clear_menu_caches(
        mode_key: str, mode: MenuMode
    ) -> tuple[str, int, list[str]]:
        count, total = clear_menu_caches(mode)
        return (mode_key, count, total)

    @Slot()
    def _on_reset_caches_clicked(self):
        """Deletes binary pointer/pattern cache files for the active edition."""
        mode = self.get_mode()
        mode_key = getattr(mode, "key", str(mode))

        self.worker_manager.run_exclusive(
            f"clear_menu_caches_{mode_key}",
            self._run_clear_menu_caches,
            mode_key,
            mode,
            on_finished=self._on_reset_caches_finished,
            on_error=self._on_task_error,
        )

    @Slot(object)
    def _on_reset_caches_finished(self, result: tuple[str, int, list[str]]):
        mode_key, count, _ = result
        curr_mode = self.get_mode()
        if getattr(curr_mode, "key", str(curr_mode)) != mode_key:
            return
        if count > 0:
            msg = self.loc_manager.tr(
                "Settings.Notify.CachesClearedMsg",
                "{0} cache file(s) cleared successfully.",
            ).format(count)
            self._notify(
                self.loc_manager.tr(
                    "Settings.Notify.CachesClearedTitle", "Caches Cleared"
                ),
                msg,
                icon_type="success",
            )
        else:
            self._notify(
                self.loc_manager.tr("Common.Info", "Information"),
                self.loc_manager.tr(
                    "Settings.Notify.NoCachesMsg", "No cache files found to clear."
                ),
                icon_type="info",
            )

    @Slot()
    def _on_open_log_clicked(self):
        """Opens the active edition's cout.log file if it exists."""
        mode = self.get_mode()
        log_path = os.path.join(mode.appdata_dir, "cout.log")
        if os.path.isfile(log_path):
            try:
                os.startfile(log_path)
            except OSError as e:
                logger.error(f"Could not open log file '{log_path}': {e}")
                self._notify(
                    self.loc_manager.tr("Common.Error", "Error"),
                    self.loc_manager.tr(
                        "Settings.Paths.OpenLogFailed",
                        "Could not open log file:\n{0}",
                    ).format(e),
                    icon_type="error",
                )
        else:
            fmt = self.loc_manager.tr(
                "Settings.Notify.FileMissing",
                "File does not exist yet:\n{0}",
            )
            self._notify(
                self.loc_manager.tr("Common.Info", "Information"),
                fmt.format(log_path),
                icon_type="info",
            )

    @Slot()
    def _on_disable_all_scripts_clicked(self):
        """Moves all enabled Lua scripts to the disabled folder."""
        mode = self.get_mode()
        moved = bulk_toggle_scripts(mode, disable=True)
        self._refresh_lua_lists()
        if moved > 0:
            self._notify(
                self.loc_manager.tr("Settings.Header.Lua", "Lua Settings"),
                self.loc_manager.tr(
                    "Settings.Notify.LuaSafeModeEnabled",
                    "{0} script(s) moved to disabled (Safe Mode).",
                ).format(moved),
                icon_type="info",
            )

    @Slot()
    def _on_enable_all_scripts_clicked(self):
        """Moves all disabled Lua scripts back to the active scripts folder."""
        mode = self.get_mode()
        moved = bulk_toggle_scripts(mode, disable=False)
        self._refresh_lua_lists()
        if moved > 0:
            self._notify(
                self.loc_manager.tr("Settings.Header.Lua", "Lua Settings"),
                self.loc_manager.tr(
                    "Settings.Notify.LuaSafeModeDisabled",
                    "{0} script(s) re-enabled.",
                ).format(moved),
                icon_type="success",
            )

    @Slot(bool)
    def _on_auto_close_toggled(self, checked: bool):
        """Called when the user toggles the auto-close switch."""
        get_config().set("inject.auto_close", checked)

    @Slot(bool)
    def _on_sound_feedback_toggled(self, checked: bool):
        """Called when the user toggles the sound feedback switch."""
        get_config().set("inject.sound_feedback", checked)

    def _apply_gta_dir(self, directory: str) -> bool:
        """Validates and applies a custom GTA V directory. Returns True if valid, False otherwise."""
        clean_dir = os.path.normpath(directory.strip().strip('"').strip("'"))
        if os.path.isfile(clean_dir) and os.path.basename(clean_dir).lower() in (
            "playgtav.exe",
            "gta5.exe",
            "gta5_enhanced.exe",
        ):
            clean_dir = os.path.dirname(clean_dir)
        if not os.path.isdir(clean_dir):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNotFound", "Path does not exist."
                )
            )
            return False
        gta_exes = ("playgtav.exe", "gta5.exe", "gta5_enhanced.exe")
        try:
            present = {f.lower() for f in os.listdir(clean_dir)}
        except OSError as e:
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorAccess", "Cannot access folder: {0}"
                ).format(e)
            )
            return False
        if not present.intersection(gta_exes):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNoGta",
                    "No GTA V executable found in this folder.",
                )
            )
            return False
        get_config().set("paths.gta_dir", clean_dir)
        self._cached_gta_dir.clear()
        self.gta_dir_edit.setText(clean_dir)
        self._update_nobattleye_toggle_state()
        return True

    def _apply_custom_dll(self, file_path: str) -> bool:
        """Validates and applies a custom DLL file path. Returns True if valid, False otherwise."""
        clean_path = os.path.normpath(file_path.strip().strip('"').strip("'"))
        if not os.path.isfile(clean_path):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNotFound", "Path does not exist."
                )
            )
            return False
        if not clean_path.lower().endswith(".dll"):
            self._path_error(
                self.loc_manager.tr(
                    "Settings.Paths.ErrorNotDll", "Please select a .dll file."
                )
            )
            return False
        get_config().set("paths.custom_dll", clean_path)
        self.custom_dll_edit.setText(clean_path)
        return True

    @Slot()
    def _on_gta_dir_editing_finished(self):
        """Slot for manual keyboard/paste entry in the GTA V directory field."""
        text = self.gta_dir_edit.text().strip().strip('"').strip("'")
        current = get_config().get("paths.gta_dir") or ""
        if text == current:
            if self.gta_dir_edit.text() != current:
                self.gta_dir_edit.setText(current)
            return
        if not text:
            self._clear_path("paths.gta_dir")
            return
        if not self._apply_gta_dir(text):
            self.gta_dir_edit.setText(current)

    @Slot()
    def _on_custom_dll_editing_finished(self):
        """Slot for manual keyboard/paste entry in the custom DLL path field."""
        text = self.custom_dll_edit.text().strip().strip('"').strip("'")
        current = get_config().get("paths.custom_dll") or ""
        if text == current:
            if self.custom_dll_edit.text() != current:
                self.custom_dll_edit.setText(current)
            return
        if not text:
            self._clear_path("paths.custom_dll")
            return
        if not self._apply_custom_dll(text):
            self.custom_dll_edit.setText(current)

    @Slot()
    def _browse_gta_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            self.loc_manager.tr("Settings.Paths.GtaDir", "GTA V install folder"),
        )
        if not directory:
            return
        self._apply_gta_dir(directory)

    @Slot()
    def _browse_custom_dll(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.loc_manager.tr("Settings.Paths.CustomDll", "Custom menu DLL"),
            "",
            "DLL files (*.dll)",
        )
        if not file_path:
            return
        self._apply_custom_dll(file_path)

    def _clear_path(self, key: str):
        get_config().set(key, None)
        if key == "paths.gta_dir":
            self._cached_gta_dir.clear()
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

    @Slot()
    def _open_risks_page(self):
        """Navigates to the Risks page in MainWindow."""
        main_win = self.window()
        show_fn = getattr(main_win, "show_risks_page", None)
        if callable(show_fn):
            show_fn()

    def _open_link(self, path_or_url: str):
        """Opens a local folder path or a web URL."""
        if path_or_url.lower().startswith(("http://", "https://")):
            webbrowser.open(path_or_url)
        elif os.path.isdir(path_or_url):
            try:
                os.startfile(path_or_url)
            except OSError as e:
                logger.error(f"Could not open path '{path_or_url}': {e}")
                self._notify(
                    self.loc_manager.tr("Common.Error", "Error"),
                    self.loc_manager.tr(
                        "Settings.Notify.OpenFolderFailed",
                        "Could not open folder:\n{0}",
                    ).format(e),
                    icon_type="error",
                )
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
        mode = self.get_mode()
        settings_file = mode.settings_file
        is_legacy = mode.key == "legacy"

        # In Enhanced (YimMenuV2), auto-reload and external console are not supported.
        self.auto_reload_toggle.setInteractive(is_legacy)
        self.debug_console_toggle.setInteractive(is_legacy)
        self.auto_reload_label.setEnabled(True)
        self.debug_console_label.setEnabled(True)

        base_auto_reload = self.loc_manager.tr(
            "Settings.Lua.AutoReload", "Auto-reload changed scripts"
        )
        base_debug_console = self.loc_manager.tr(
            "Settings.Other.DebugConsole", "Enable External Debug Console"
        )

        if not is_legacy:
            legacy_tooltip = self.loc_manager.tr(
                "Settings.Notice.LegacyOnly", "Only available in YimMenu Legacy"
            )
            legacy_badge = self.loc_manager.tr(
                "Settings.Badge.LegacyOnly", "Legacy only"
            )
            self.auto_reload_label.setText(f"{base_auto_reload} ({legacy_badge})")
            self.debug_console_label.setText(f"{base_debug_console} ({legacy_badge})")
            self.auto_reload_label.setProperty("unsupported", "true")
            self.debug_console_label.setProperty("unsupported", "true")
            self.auto_reload_label.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.debug_console_label.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.auto_reload_toggle.setToolTip(legacy_tooltip)
            self.auto_reload_label.setToolTip(legacy_tooltip)
            self.debug_console_toggle.setToolTip(legacy_tooltip)
            self.debug_console_label.setToolTip(legacy_tooltip)
        else:
            self.auto_reload_label.setText(base_auto_reload)
            self.debug_console_label.setText(base_debug_console)
            self.auto_reload_label.setProperty("unsupported", "false")
            self.debug_console_label.setProperty("unsupported", "false")
            self.auto_reload_label.setCursor(Qt.CursorShape.ArrowCursor)
            self.debug_console_label.setCursor(Qt.CursorShape.ArrowCursor)
            auto_reload_tooltip = self.loc_manager.tr(
                "Settings.Lua.Tooltip.AutoReload",
                "Automatically re-apply changes when Lua script files are saved",
            )
            debug_tooltip = self.loc_manager.tr(
                "Settings.Other.Tooltip.Debug",
                "Show YimMenu's external console window for detailed logs and debugging",
            )
            self.auto_reload_toggle.setToolTip(auto_reload_tooltip)
            self.auto_reload_label.setToolTip(auto_reload_tooltip)
            self.debug_console_toggle.setToolTip(debug_tooltip)
            self.debug_console_label.setToolTip(debug_tooltip)

        for lbl in (self.auto_reload_label, self.debug_console_label):
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)

        is_enabled = is_legacy and settings_manager.get_setting(
            "lua.enable_auto_reload_changed_scripts",
            default=False,
            settings_file=settings_file,
        )
        self.auto_reload_toggle.blockSignals(True)
        self.auto_reload_toggle.setChecked(bool(is_enabled))
        self.auto_reload_toggle.blockSignals(False)

        is_debug_enabled = is_legacy and settings_manager.get_setting(
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
        self._update_open_folder_button()

    def _update_open_folder_button(self):
        """Updates the text and tooltip of the open folder and log buttons to match the active mode."""
        mode = self.get_mode()
        if mode.key == "enhanced":
            text = self.loc_manager.tr(
                "Settings.Btn.OpenYimV2Folder", "Open YimMenuV2 Folder"
            )
            tooltip = self.loc_manager.tr(
                "Settings.Tooltip.OpenYimV2Folder",
                "Open YimMenuV2 folder (%APPDATA%/YimMenuV2)",
            )
            log_text = self.loc_manager.tr(
                "Settings.Btn.OpenV2Log", "Open YimMenuV2 Log"
            )
        else:
            text = self.loc_manager.tr(
                "Settings.Btn.OpenYimFolder", "Open YimMenu Folder"
            )
            tooltip = self.loc_manager.tr(
                "Settings.Tooltip.OpenYimFolder",
                "Open YimMenu folder (%APPDATA%/YimMenu)",
            )
            log_text = self.loc_manager.tr("Settings.Btn.OpenLog", "Open YimMenu Log")
        self.btn_open_folder.setText(f"  {text}")
        self.btn_open_folder.setToolTip(tooltip)
        if hasattr(self, "btn_open_log"):
            self.btn_open_log.setText(f"  {log_text}")

    def _write_yim_setting(self, key_path: str, value, toggle=None):
        """Writes into the active edition's settings.json. YimMenuV2's file is
        never created from scratch (unknown schema — YMU does not own it)."""
        mode = self.get_mode()
        ok = settings_manager.set_setting(
            key_path,
            value,
            settings_file=mode.settings_file,
            create_if_missing=(mode.key == "legacy"),
        )
        if not ok:
            if toggle is not None:
                toggle.blockSignals(True)
                toggle.setChecked(not value)
                toggle.blockSignals(False)

            if mode.key != "legacy":
                msg = self.loc_manager.tr(
                    "Settings.Notify.V2FileMissing",
                    "YimMenuV2 has no settings.json yet.\nInject and run it once, then try again.",
                )
                self._notify(
                    self.loc_manager.tr("Common.Info", "Information"),
                    msg,
                    icon_type="info",
                )
            else:
                msg = self.loc_manager.tr(
                    "Settings.Notify.SettingWriteFailed",
                    "Failed to save setting to settings.json.",
                )
                self._notify(
                    self.loc_manager.tr("Common.Error", "Error"),
                    msg,
                    icon_type="error",
                )

    @Slot(bool)
    def _on_auto_reload_toggled(self, checked: bool):
        """Called when the user clicks the auto-reload toggle."""
        if self.get_mode().key != "legacy":
            return
        self._write_yim_setting(
            "lua.enable_auto_reload_changed_scripts",
            checked,
            toggle=getattr(self, "auto_reload_toggle", None),
        )

    @Slot(bool)
    def _on_debug_console_toggled(self, checked: bool):
        """Called when the user clicks the debug console toggle."""
        if self.get_mode().key != "legacy":
            return
        self._write_yim_setting(
            "debug.external_console",
            checked,
            toggle=getattr(self, "debug_console_toggle", None),
        )

    def _on_toggle_focus_changed(self, label: QLabel, has_focus: bool):
        """Updates the style of a label based on the focus state of its toggle."""
        if has_focus:
            if self.theme_manager.current_theme == "dark":
                label.setStyleSheet("text-decoration: underline; color: #FFFFFF;")
            else:
                label.setStyleSheet("text-decoration: underline; color: #000000;")
        else:
            label.setStyleSheet("")

    @Slot()
    def _refresh_lua_lists(self):
        """Fetches the active edition's script lists, updates UI, and plays a
        brief feedback animation."""

        self.btn_refresh_luas.start_animation(duration=500)
        self.btn_refresh_luas.setEnabled(False)

        try:
            for lst in (self.disabled_scripts_list, self.enabled_scripts_list):
                for i in range(lst.count()):
                    item = lst.item(i)
                    w = lst.itemWidget(item)
                    if isinstance(w, LuaScriptItemWidget):
                        with contextlib.suppress(RuntimeError, TypeError):
                            w.actionClicked.disconnect()
                        w.cleanup()
                    if w is not None:
                        lst.removeItemWidget(item)
                        w.deleteLater()
                lst.clear()

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

            scripts = (
                lua_manager.get_scripts(mode.scripts_dir, mode.disabled_scripts_dir)
                if available
                else {"enabled": [], "disabled": []}
            )

            is_rtl = (
                self.isRightToLeft()
                or getattr(self.theme_manager, "is_rtl", False)
                or (self.loc_manager is not None and self.loc_manager.is_rtl())
            )

            enable_tooltip = self.loc_manager.tr(
                "Settings.Lua.Tooltip.Enable", "Enable selected script(s)"
            )
            disable_tooltip = self.loc_manager.tr(
                "Settings.Lua.Tooltip.Disable", "Disable selected script(s)"
            )

            for script_name in scripts["disabled"]:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, script_name)
                item.setSizeHint(QSize(0, LUA_ROW_HEIGHT))
                widget = LuaScriptItemWidget(
                    script_name=script_name,
                    direction="enable",
                    theme_manager=self.theme_manager,
                    parent=self.disabled_scripts_list,
                    item=item,
                    is_rtl=is_rtl,
                    tooltip=enable_tooltip,
                )
                widget.actionClicked.connect(self._enable_single_script)
                self.disabled_scripts_list.addItem(item)
                self.disabled_scripts_list.setItemWidget(item, widget)

            for script_name in scripts["enabled"]:
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, script_name)
                item.setSizeHint(QSize(0, LUA_ROW_HEIGHT))
                widget = LuaScriptItemWidget(
                    script_name=script_name,
                    direction="disable",
                    theme_manager=self.theme_manager,
                    parent=self.enabled_scripts_list,
                    item=item,
                    is_rtl=is_rtl,
                    tooltip=disable_tooltip,
                )
                widget.actionClicked.connect(self._disable_single_script)
                self.enabled_scripts_list.addItem(item)
                self.enabled_scripts_list.setItemWidget(item, widget)

            disabled_base = self.loc_manager.tr("Settings.Lua.ListDisabled", "Disabled")
            enabled_base = self.loc_manager.tr("Settings.Lua.ListEnabled", "Enabled")
            disabled_count = len(scripts["disabled"])
            enabled_count = len(scripts["enabled"])

            if hasattr(self, "disabled_header_label"):
                self.disabled_header_label.setText(
                    f"{disabled_base} ({disabled_count})"
                    if available
                    else disabled_base
                )
            if hasattr(self, "enabled_header_label"):
                self.enabled_header_label.setText(
                    f"{enabled_base} ({enabled_count})" if available else enabled_base
                )

            if hasattr(self, "btn_disable_all_scripts"):
                self.btn_disable_all_scripts.setEnabled(available and enabled_count > 0)
            if hasattr(self, "btn_enable_all_scripts"):
                self.btn_enable_all_scripts.setEnabled(available and disabled_count > 0)

            row_height = LUA_ROW_HEIGHT
            frame_overhead = LUA_LIST_FRAME_OVERHEAD
            min_items = LUA_LIST_MIN_ROWS
            max_items = LUA_LIST_MAX_ROWS
            item_count = max(disabled_count, enabled_count)
            visible_items = max(min_items, min(max_items, item_count))
            final_height = visible_items * row_height + frame_overhead
            self.disabled_scripts_list.setFixedHeight(final_height)
            self.enabled_scripts_list.setFixedHeight(final_height)
        except Exception:
            logger.exception("Failed to refresh Lua script lists")
        finally:
            QTimer.singleShot(500, self._enable_btn_refresh_luas)

    def _get_item_script_name(self, item: QListWidgetItem | None) -> str:
        """Retrieves script name from UserRole data or item text."""
        if not item:
            return ""
        data = item.data(Qt.ItemDataRole.UserRole)
        return str(data) if data else item.text()

    @Slot(QListWidgetItem)
    def _on_disabled_item_double_clicked(self, item: QListWidgetItem):
        name = self._get_item_script_name(item)
        if name:
            self._enable_single_script(name)

    @Slot(QListWidgetItem)
    def _on_enabled_item_double_clicked(self, item: QListWidgetItem):
        name = self._get_item_script_name(item)
        if name:
            self._disable_single_script(name)

    @Slot(str)
    def _enable_single_script(self, script_name: str):
        if not script_name:
            return
        mode = self.get_mode()
        lua_manager.enable_script(
            mode.scripts_dir, mode.disabled_scripts_dir, script_name
        )
        self._refresh_lua_lists()

    @Slot(str)
    def _disable_single_script(self, script_name: str):
        if not script_name:
            return
        mode = self.get_mode()
        lua_manager.disable_script(
            mode.scripts_dir, mode.disabled_scripts_dir, script_name
        )
        self._refresh_lua_lists()

    def _enable_selected_scripts(self):
        """Moves selected scripts from the disabled list to the enabled list."""
        selected_items = self.disabled_scripts_list.selectedItems()
        if not selected_items and self.disabled_scripts_list.currentItem():
            selected_items = [self.disabled_scripts_list.currentItem()]
        if not selected_items:
            return

        mode = self.get_mode()
        for item in selected_items:
            name = self._get_item_script_name(item)
            if name:
                lua_manager.enable_script(
                    mode.scripts_dir, mode.disabled_scripts_dir, name
                )

        self._refresh_lua_lists()

    def _disable_selected_scripts(self):
        """Moves selected scripts from the enabled list to the disabled list."""
        selected_items = self.enabled_scripts_list.selectedItems()
        if not selected_items and self.enabled_scripts_list.currentItem():
            selected_items = [self.enabled_scripts_list.currentItem()]
        if not selected_items:
            return

        mode = self.get_mode()
        for item in selected_items:
            name = self._get_item_script_name(item)
            if name:
                lua_manager.disable_script(
                    mode.scripts_dir, mode.disabled_scripts_dir, name
                )

        self._refresh_lua_lists()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handles keyboard shortcuts like Return/Enter/Space for Lua script lists."""
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space)
        ):
            if watched == self.disabled_scripts_list:
                self._enable_selected_scripts()
                return True
            if watched == self.enabled_scripts_list:
                self._disable_selected_scripts()
                return True
        return super().eventFilter(watched, event)

    @Slot()
    def _handle_check_for_updates(self):
        """Starts the background task to check for YMU updates."""
        self.btn_check_for_updates.setEnabled(False)
        self.btn_check_for_updates.start_animation()

        started = self.worker_manager.run_exclusive(
            "ymu_update",
            update_checker.check_for_updates,
            on_finished=self._on_update_check_finished,
            on_error=self._on_task_error,
        )
        if not started:
            self.btn_check_for_updates.setEnabled(True)
            self.btn_check_for_updates.stop_animation()

    @Slot(object)
    def _on_update_check_finished(self, result):
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.setEnabled(True)

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
            QTimer.singleShot(5000, self._reset_check_updates_btn_text)

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

    @Slot()
    def _on_fetch_lang_clicked(self):
        """Start the manual download and animation."""
        self.btn_update_lang.setEnabled(False)
        self.btn_update_lang.start_animation(duration=500)
        self.loc_manager.fetch_updates()

    @Slot(bool, str, bool)
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
                self._notify(title, message, icon_type="success")
        else:
            self._notify(
                self.loc_manager.tr("Common.Error", "Error"), message, icon_type="error"
            )

    @Slot()
    def _on_language_index_changed(self):
        """Starts the debounce timer when language selection changes in the UI."""
        self._lang_debounce_timer.start()

    @Slot()
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

    @Slot(Exception)
    def _on_task_error(self, error: Exception):
        """A generic callback to handle any errors from the worker tasks."""
        self.btn_check_for_updates.stop_animation()
        self.btn_check_for_updates.reset_progress()
        self.btn_check_for_updates.setText(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates")
        )
        self.btn_check_for_updates.setEnabled(True)

        logger.error(f"A settings page task failed in the background: {error}")
        self._notify(
            self.loc_manager.tr("Common.Error", "Error"),
            f"{self.loc_manager.tr('Common.UnexpectedError', 'An unexpected error occurred')}: {error}",
            icon_type="error",
        )

    @Slot()
    def _on_theme_button_clicked(self) -> None:
        QTimer.singleShot(0, self._update_theme_buttons_icons)

    @Slot()
    def _update_theme_buttons_icons(self) -> None:
        for b in self.theme_group.buttons():
            if isinstance(b, StatefulButton):
                b.updateIcon()

    @Slot()
    def _apply_dark_theme(self) -> None:
        self.theme_manager.apply_theme("dark")

    @Slot()
    def _apply_light_theme(self) -> None:
        self.theme_manager.apply_theme("light")

    @Slot(bool)
    def _on_any_toggle_focus_changed(self, has_focus: bool) -> None:
        sender = self.sender()
        if not isinstance(sender, ToggleSwitch):
            return
        label_map = {
            self.auto_reload_toggle: self.auto_reload_label,
            self.debug_console_toggle: self.debug_console_label,
            self.nobattleye_toggle: self.nobattleye_label,
            self.auto_close_toggle: self.auto_close_label,
            self.sound_feedback_toggle: self.sound_feedback_label,
        }
        label = label_map.get(sender)
        if label:
            self._on_toggle_focus_changed(label, has_focus)

    @Slot()
    def _on_open_appdata_clicked(self) -> None:
        self._open_link(self.get_mode().appdata_dir)

    @Slot()
    def _on_open_ymu_appdata_clicked(self) -> None:
        self._open_link(YMU_APPDATA_DIR)

    @Slot()
    def _on_report_bug_clicked(self) -> None:
        self._open_link(
            "https://github.com/NiiV3AU/YMU/issues/new?template=bug_report.yaml"
        )

    @Slot()
    def _on_request_feature_clicked(self) -> None:
        self._open_link(
            "https://github.com/NiiV3AU/YMU/issues/new?template=feature_request.yaml"
        )

    @Slot()
    def _on_open_scripts_folder_clicked(self) -> None:
        self._open_link(self.get_mode().scripts_dir)

    @Slot()
    def _on_discover_luas_clicked(self) -> None:
        self._open_link("https://github.com/orgs/YimMenu-Lua/repositories")

    @Slot()
    def _on_clear_gta_clicked(self) -> None:
        self._clear_path("paths.gta_dir")

    @Slot()
    def _on_clear_dll_clicked(self) -> None:
        self._clear_path("paths.custom_dll")

    @Slot()
    def _enable_btn_refresh_luas(self) -> None:
        self.btn_refresh_luas.setEnabled(True)

    @Slot()
    def _reset_check_updates_btn_text(self) -> None:
        self.btn_check_for_updates.setText(
            self.loc_manager.tr("Settings.Btn.CheckUpdates", "Check for YMU Updates")
        )
