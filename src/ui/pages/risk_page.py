import os
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from core.paths import resource_path
from ui.widgets.buttons import StatefulButton

if TYPE_CHECKING:
    from ui.i18n.localization_manager import LocalizationManager
    from ui.styles.theme_manager import ThemeManager


class RiskPage(QWidget):
    """A page which shows risks and warnings as well as links to repos and FSL."""

    def __init__(
        self,
        theme_manager: "ThemeManager",
        loc_manager: "LocalizationManager",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.loc_manager = loc_manager

        title_text = self.loc_manager.tr("Risk.Title", "ATTENTION")
        self.title_label = QLabel(title_text)
        self.title_label.setObjectName("RiskTitleLabel")

        info_text = self.loc_manager.tr(
            "Risk.Info",
            "Always use YMU and YimMenu with BattlEye DISABLED.\nUsing mods online carries a risk of being banned.",
        )
        self.info_label = QLabel(info_text)
        self.info_label.setObjectName("RiskInfoLabel")
        self.info_label.setWordWrap(True)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }

        icon_path = resource_path(os.path.join("assets", "icons", "external-link.svg"))

        self.yim_official_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimOfficial', 'Official YimMenu GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=icon_path,
            **link_button_colors,
        )
        self.yim_official_repo_button.setObjectName("LinkButton")
        self.yim_official_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimOfficial",
                "Open the official YimMenu GitHub repository",
            )
        )
        self.yim_official_repo_button.clicked.connect(self._open_yim_official)

        self.yim_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimLegacy', 'YimMenu (Legacy) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=icon_path,
            **link_button_colors,
        )
        self.yim_repo_button.setObjectName("LinkButton")
        self.yim_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimLegacy", "Open the YimMenu (Legacy) GitHub repository"
            )
        )
        self.yim_repo_button.clicked.connect(self._open_yim_legacy)

        self.yimv2_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimV2', 'YimMenuV2 (Enhanced) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        self.yimv2_repo_button.setObjectName("LinkButton")
        self.yimv2_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimV2", "Open the YimMenuV2 (Enhanced) GitHub repository"
            )
        )
        self.yimv2_repo_button.clicked.connect(self._open_yim_v2)

        fsl_label = self.loc_manager.tr("Risk.Btn.FSL", "FSL's UC-Thread")
        self.fsl_thread_button = StatefulButton(
            f"  {fsl_label}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        self.fsl_thread_button.setObjectName("LinkButton")
        self.fsl_thread_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.FSL",
                "Open the FSL thread on UnknownCheats for download & support",
            )
        )
        self.fsl_thread_button.clicked.connect(self._open_fsl)

        self.card_frame = QFrame()
        self.card_frame.setObjectName("CardFrame")

        card_layout = QVBoxLayout(self.card_frame)
        card_layout.setSpacing(16)
        card_layout.addWidget(self.title_label)
        card_layout.addWidget(self.info_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(self.yim_official_repo_button)
        card_layout.addWidget(self.yim_repo_button)
        card_layout.addWidget(self.yimv2_repo_button)
        card_layout.addWidget(self.fsl_thread_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(40, 0, 40, 0)
        main_layout.addStretch()
        main_layout.addWidget(self.card_frame)
        main_layout.addStretch()

        self.setTabOrder(self.yim_official_repo_button, self.yim_repo_button)
        self.setTabOrder(self.yim_repo_button, self.yimv2_repo_button)
        self.setTabOrder(self.yimv2_repo_button, self.fsl_thread_button)

    @Slot()
    def _open_yim_official(self) -> None:
        webbrowser.open("https://github.com/YimMenu/YimMenu")

    @Slot()
    def _open_yim_legacy(self) -> None:
        webbrowser.open("https://github.com/Mr-X-GTA/YimMenu")

    @Slot()
    def _open_yim_v2(self) -> None:
        webbrowser.open("https://github.com/YimMenu/YimMenuV2")

    @Slot()
    def _open_fsl(self) -> None:
        webbrowser.open(
            "https://www.unknowncheats.me/forum/grand-theft-auto-v/616977-fsl-local-gtao-saves.html"
        )
