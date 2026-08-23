# risk_page.py - Displays warnings, risks, and project repository links.
import os
import webbrowser
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from paths import resource_path
from ui.widgets.buttons import StatefulButton

if TYPE_CHECKING:
    from localization_manager import LocalizationManager
    from theme_manager import ThemeManager


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
        title_label = QLabel(title_text)
        title_label.setObjectName("RiskTitleLabel")

        info_text = self.loc_manager.tr(
            "Risk.Info",
            "Always use YMU and YimMenu with BattlEye DISABLED.\nUsing mods online carries a risk of being banned.",
        )
        info_label = QLabel(info_text)
        info_label.setObjectName("RiskInfoLabel")
        info_label.setWordWrap(True)

        link_button_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }

        yim_official_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimOfficial', 'Official YimMenu GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yim_official_repo_button.setObjectName("LinkButton")
        yim_official_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimOfficial",
                "Open the official YimMenu GitHub repository",
            )
        )
        yim_official_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/YimMenu/YimMenu")
        )

        yim_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimLegacy', 'YimMenu (legacy) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yim_repo_button.setObjectName("LinkButton")
        yim_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimLegacy", "Open the YimMenu (legacy) GitHub repository"
            )
        )
        yim_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/Mr-X-GTA/YimMenu")
        )

        yimv2_repo_button = StatefulButton(
            f"  {self.loc_manager.tr('Risk.Btn.YimV2', 'YimMenuV2 (enhanced) GitHub Repo')}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        yimv2_repo_button.setObjectName("LinkButton")
        yimv2_repo_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.YimV2", "Open the YimMenuV2 (enhanced) GitHub repository"
            )
        )
        yimv2_repo_button.clicked.connect(
            lambda: webbrowser.open("https://github.com/YimMenu/YimMenuV2")
        )

        fsl_label = self.loc_manager.tr("Risk.Btn.FSL", "FSL's UC-Thread")
        fsl_thread_button = StatefulButton(
            f"  {fsl_label}",
            theme_manager=self.theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_button_colors,
        )
        fsl_thread_button.setObjectName("LinkButton")
        fsl_thread_button.setToolTip(
            self.loc_manager.tr(
                "Risk.Tooltip.FSL",
                "Open the FSL thread on UnknownCheats for download & support",
            )
        )
        fsl_thread_button.clicked.connect(
            lambda: webbrowser.open(
                "https://www.unknowncheats.me/forum/grand-theft-auto-v/616977-fsl-local-gtao-saves.html"
            )
        )

        card_frame = QFrame()
        card_frame.setObjectName("CardFrame")

        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(15)
        card_layout.addWidget(title_label)
        card_layout.addWidget(info_label)
        card_layout.addSpacing(10)
        card_layout.addWidget(yim_official_repo_button)
        card_layout.addWidget(yim_repo_button)
        card_layout.addWidget(yimv2_repo_button)
        card_layout.addWidget(fsl_thread_button)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(60, 0, 60, 0)
        main_layout.addStretch()
        main_layout.addWidget(card_frame)
        main_layout.addStretch()
