# dialogs.py - Reusable modal dialogs.
import html
import os
import platform
import re
import webbrowser
from collections.abc import Callable

import PySide6
from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Slot, qVersion
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QPalette,
    QPixmap,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QScrollArea,
    QStackedWidget,
    QTabBar,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core import update_checker
from core.paths import resource_path
from ui.utils import (
    ICON_DARK_PATH,
    ICON_LIGHT_PATH,
    ICON_SVG_PATH,
    adjust_button_to_text,
    create_colored_pixmap,
)
from ui.widgets.buttons import AnimatedButton, StatefulButton


class InfoDialog(QDialog):
    """A reusable, modal dialog for showing information in tabs with dynamic resizing."""

    def __init__(self, title: str, content: dict, theme_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("InfoDialog")
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.tab_bar = QTabBar()
        self.tab_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.content_stack = QStackedWidget()

        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(self.tab_bar)
        centering_layout.addStretch()
        is_dark = theme_manager.current_theme == "dark"
        icon_path = ICON_DARK_PATH if is_dark else ICON_LIGHT_PATH
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        text_color = "#E0E0E0" if is_dark else "#121212"

        is_rtl = (
            self.isRightToLeft()
            or (parent is not None and parent.isRightToLeft())
            or (theme_manager is not None and getattr(theme_manager, "is_rtl", False))
        )
        if is_rtl:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            font_family = "Rubik, Segoe UI Arabic, Segoe UI, Tahoma, sans-serif"
        else:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            font_family = "Rubik, Segoe UI, Segoe UI Arabic, Yu Gothic UI, Microsoft YaHei UI, Microsoft JhengHei UI, Malgun Gothic, Nirmala UI, Leelawadee UI, Meiryo UI, Meiryo, sans-serif"

        dir_attr = "rtl" if is_rtl else "ltr"
        text_align = "right" if is_rtl else "left"

        for tab_title, tab_content in content.items():
            self.tab_bar.addTab(tab_title)
            lines = tab_content.replace("\r\n", "\n").split("\n")
            paragraphs = "".join(
                f"<p dir='{dir_attr}' align='{text_align}' style='margin:0; padding:0; font-family:{font_family}; font-size:16px; color:{text_color}; line-height:{'100%' if idx == len(lines) - 1 else '140%'};'>{html.escape(line) if line.strip() else '&nbsp;'}</p>"
                for idx, line in enumerate(lines)
            )
            html_text = f"<html dir='{dir_attr}'><body dir='{dir_attr}'>{paragraphs}</body></html>"

            content_label = QLabel(html_text)
            content_label.setTextFormat(Qt.TextFormat.RichText)
            content_label.setLayoutDirection(
                Qt.LayoutDirection.RightToLeft
                if is_rtl
                else Qt.LayoutDirection.LeftToRight
            )
            content_label.setAlignment(
                (Qt.AlignmentFlag.AlignRight if is_rtl else Qt.AlignmentFlag.AlignLeft)
                | Qt.AlignmentFlag.AlignVCenter
            )
            content_label.setWordWrap(True)
            content_label.setOpenExternalLinks(True)

            page_widget = QWidget()
            page_layout = QHBoxLayout(page_widget)
            page_layout.setContentsMargins(30, 20, 30, 20)
            page_layout.addStretch()
            page_layout.addWidget(content_label)
            page_layout.addStretch()

            self.content_stack.addWidget(page_widget)

        self.tab_bar.currentChanged.connect(self._on_tab_changed)

        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)
        main_layout.addLayout(centering_layout)
        main_layout.addWidget(self.content_stack)

        if self.tab_bar.count() > 0:
            self.content_stack.setCurrentIndex(0)

    def showEvent(self, event):
        super().showEvent(event)
        self.adjustSize()

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        self.content_stack.setCurrentIndex(index)
        QTimer.singleShot(0, self._adjust_size_deferred)

    @Slot()
    def _adjust_size_deferred(self) -> None:
        self.adjustSize()


class HoverableRichLabel(QLabel):
    """Rich text label that dynamically toggles underline styling on hovered links."""

    def __init__(
        self,
        html_builder,
        is_rtl: bool,
        text_color: str,
        on_link_activated: Callable[[str], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._html_builder = html_builder
        self._on_link_activated_cb = on_link_activated
        self._hovered_url = ""
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setOpenExternalLinks(False)
        self.setMouseTracking(True)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl else Qt.LayoutDirection.LeftToRight
        )
        self.setAlignment(
            (Qt.AlignmentFlag.AlignRight if is_rtl else Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignTop
        )
        self.setStyleSheet(f"color: {text_color}; background: transparent;")
        self.linkHovered.connect(self._on_link_hovered)
        self.linkActivated.connect(self._on_link_activated)
        self._refresh()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if self._hovered_url:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        if self._hovered_url:
            self._hovered_url = ""
            self._refresh()
        self.unsetCursor()

    @Slot(str)
    def _on_link_hovered(self, url: str):
        if self._hovered_url != url:
            self._hovered_url = url
            self._refresh()

    @Slot(str)
    def _on_link_activated(self, url: str):
        if self._on_link_activated_cb:
            self._on_link_activated_cb(url)
        else:
            target = url.split("#", maxsplit=1)[0] if "#" in url else url
            if target:
                webbrowser.open(target)

    def _refresh(self):
        self.setText(self._html_builder(self._hovered_url))
        if self._hovered_url:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.unsetCursor()


_KNOWN_LICENSE_HEADERS = {
    "apache license",
    "gnu general public license",
    "gnu lesser general public license",
    "terms and conditions for use, reproduction, and distribution",
    "terms and conditions for copying, distribution and modification",
    "end of terms and conditions",
    "no warranty",
    "preamble",
    "definitions",
    "permission & conditions",
    "termination",
    "disclaimer",
}


def format_plain_license(raw_text: str, text_color: str, is_dark: bool) -> str:
    """Format plain-text license into HTML with centered title/section headers."""
    lines = raw_text.splitlines()
    body_parts = []
    for line in lines:
        stripped = line.strip()
        lead = len(line) - len(line.lstrip(" "))
        is_title = bool(
            stripped
            and (
                stripped.lower() in _KNOWN_LICENSE_HEADERS
                or (len(stripped) <= 70 and lead >= 12)
            )
        )

        if stripped.startswith("=") and len(stripped) >= 20:
            hr_color = "#3A3A3A" if is_dark else "#D0D7DE"
            body_parts.append(
                f"<hr style='border:0; border-top:1px solid {hr_color}; margin:16px 0;'>"
            )
        elif is_title:
            body_parts.append(
                f"<p align='center' style='font-weight:700; margin:8px 0;'>{html.escape(stripped)}</p>"
            )
        else:
            if not stripped:
                body_parts.append("<p style='margin:4px 0;'>&nbsp;</p>")
            else:
                body_parts.append(
                    f"<p style='margin:1px 0; white-space:pre-wrap;'>{html.escape(line)}</p>"
                )

    content_html = "".join(body_parts)
    font_family = "Consolas, 'Courier New', monospace"
    bg_color = "#242424" if is_dark else "#F8F9FA"
    return (
        f'<html><body style="background-color:{bg_color}; font-family:{font_family}; font-size:12px; '
        f'line-height:140%; color:{text_color}; margin:0; padding:0;">'
        f"{content_html}</body></html>"
    )


class LicenseTextBrowser(QTextBrowser):
    """QTextBrowser subclass that handles in-document markdown anchor jumps and external links."""

    def doSetSource(
        self,
        name: QUrl | str,
        type: QTextDocument.ResourceType = QTextDocument.ResourceType.UnknownResource,  # noqa: A002
    ) -> None:
        url_obj = name if isinstance(name, QUrl) else QUrl(name)
        url_str = url_obj.toString()
        if url_str.startswith("#") or url_obj.hasFragment():
            slug = url_obj.fragment() if url_obj.hasFragment() else url_str.lstrip("#")
            clean_target = re.sub(r"[^a-z0-9]+", " ", slug.lower()).strip()
            doc = self.document()
            block = doc.begin()
            while block.isValid():
                clean_block = re.sub(r"[^a-z0-9]+", " ", block.text().lower()).strip()
                if clean_block == clean_target:
                    cursor = QTextCursor(block)
                    self.setTextCursor(cursor)
                    r = self.cursorRect(cursor)
                    self.verticalScrollBar().setValue(
                        max(0, self.verticalScrollBar().value() + r.top() - 10)
                    )
                    return
                block = block.next()
        elif url_str.startswith(("http://", "https://")):
            webbrowser.open(url_str)


class LicenseViewerDialog(QDialog):
    """Modal dialog displaying bundled license text in a rich text, markdown, or monospace viewer."""

    def __init__(
        self,
        title: str,
        text_content: str,
        online_url: str | None,
        theme_manager,
        loc_manager,
        is_markdown: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("LicenseViewerDialog")
        dialog_title = f"{title} - {loc_manager.tr('About.TabLicenses', 'Licenses')}"
        self.setWindowTitle(dialog_title)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        screen = self.screen() or QGuiApplication.primaryScreen()
        avail_geo = screen.availableGeometry() if screen else None
        if avail_geo:
            target_width = min(680, max(420, avail_geo.width() - 40))
            target_height = min(560, max(320, avail_geo.height() - 40))
        else:
            target_width = 680
            target_height = 560

        self.resize(target_width, target_height)
        self.setMinimumSize(420, 320)

        is_dark = theme_manager.current_theme == "dark"
        icon_path = ICON_DARK_PATH if is_dark else ICON_LIGHT_PATH
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        is_rtl = (
            self.isRightToLeft()
            or (parent is not None and parent.isRightToLeft())
            or (theme_manager is not None and getattr(theme_manager, "is_rtl", False))
        )
        if is_rtl:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            font_family = "Rubik, Segoe UI Arabic, Segoe UI, Tahoma, sans-serif"
        else:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            font_family = (
                "Rubik, Segoe UI, Segoe UI Arabic, Yu Gothic UI, Microsoft YaHei UI, "
                "Microsoft JhengHei UI, Malgun Gothic, Nirmala UI, Leelawadee UI, Meiryo UI, Meiryo, sans-serif"
            )

        text_color = "#E0E0E0" if is_dark else "#121212"

        # Header Row: Title on the left/right, and LinkButton next to it
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setWordWrap(True)
        title_label.setStyleSheet(
            f"font-size: 16px; font-weight: 700; color: {text_color}; font-family: {font_family};"
        )
        header_layout.addWidget(title_label, 1, Qt.AlignmentFlag.AlignVCenter)

        # External Link Button in Header (matching About section LinkButtons)
        link_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }
        self.online_url = online_url
        self.btn_open_online = None
        if online_url:
            self.btn_open_online = StatefulButton(
                f"  {loc_manager.tr('About.BtnOpenOnline', 'Open Online')}",
                theme_manager=theme_manager,
                icon_path=resource_path(
                    os.path.join("assets", "icons", "external-link.svg")
                ),
                **link_colors,
            )
            self.btn_open_online.setObjectName("LinkButton")
            self.btn_open_online.clicked.connect(self._on_open_online_clicked)
            header_layout.addWidget(
                self.btn_open_online, 0, Qt.AlignmentFlag.AlignVCenter
            )

        # Text Viewer (LicenseTextBrowser for selectable, rich/markdown or monospace view)
        self.text_browser = LicenseTextBrowser(self)
        self.text_browser.setObjectName("LicenseTextBrowser")
        self.text_browser.setFrameShape(QFrame.Shape.NoFrame)
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenExternalLinks(False)
        self.text_browser.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.text_edit = self.text_browser  # Compatibility alias

        # Explicit palette prevents native Windows 11 base color from showing through
        bg_qcolor = QColor("#242424" if is_dark else "#F8F9FA")
        text_qcolor = QColor("#E0E0E0" if is_dark else "#1A1D21")
        accent_qcolor = QColor("#28A745" if is_dark else "#218838")
        link_qcolor = QColor("#28A745" if is_dark else "#1A7F37")

        pal = self.text_browser.palette()
        pal.setColor(QPalette.ColorRole.Base, bg_qcolor)
        pal.setColor(QPalette.ColorRole.Text, text_qcolor)
        pal.setColor(QPalette.ColorRole.Highlight, accent_qcolor)
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        pal.setColor(QPalette.ColorRole.Link, link_qcolor)
        pal.setColor(QPalette.ColorRole.LinkVisited, link_qcolor)
        self.text_browser.setPalette(pal)
        self.text_browser.viewport().setPalette(pal)

        # Set application palette Link role so Qt markdown converter does not default to Windows 11 accent blue (#99ebff)
        app_inst = QApplication.instance()
        if isinstance(app_inst, (QApplication, QGuiApplication)):
            app_pal = app_inst.palette()
            app_pal.setColor(QPalette.ColorRole.Link, link_qcolor)
            app_pal.setColor(QPalette.ColorRole.LinkVisited, link_qcolor)
            app_inst.setPalette(app_pal)

        # Detect markdown or formatted HTML
        is_md = is_markdown or text_content.lstrip().startswith("#")
        if is_md:
            body_bg = "#242424" if is_dark else "#F8F9FA"
            body_text = "#D0D0D0" if is_dark else "#24292F"
            md_css = (
                f"body {{ background-color: {body_bg}; color: {body_text}; font-family: {font_family}; }} "
                "h1 { font-size: 18px; font-weight: 700; color: #FFFFFF; margin-top: 0; margin-bottom: 12px; } "
                "h2 { font-size: 15px; font-weight: 700; color: #FFFFFF; margin-top: 16px; margin-bottom: 8px; } "
                "h3 { font-size: 13px; font-weight: 600; color: #E0E0E0; margin-top: 12px; margin-bottom: 6px; } "
                "p, li { font-size: 13px; line-height: 150%; color: #D0D0D0; } "
                "a { color: #28A745; text-decoration: none; } "
                "blockquote { border-left: 3px solid #28A745; margin: 8px 0; padding-left: 10px; color: #9E9E9E; } "
                "code { font-family: Consolas, monospace; font-size: 12px; color: #28A745; }"
                if is_dark
                else f"body {{ background-color: {body_bg}; color: {body_text}; font-family: {font_family}; }} "
                "h1 { font-size: 18px; font-weight: 700; color: #121212; margin-top: 0; margin-bottom: 12px; } "
                "h2 { font-size: 15px; font-weight: 700; color: #121212; margin-top: 16px; margin-bottom: 8px; } "
                "h3 { font-size: 13px; font-weight: 600; color: #24292F; margin-top: 12px; margin-bottom: 6px; } "
                "p, li { font-size: 13px; line-height: 150%; color: #24292F; } "
                "a { color: #1A7F37; text-decoration: none; } "
                "blockquote { border-left: 3px solid #1A7F37; margin: 8px 0; padding-left: 10px; color: #57606A; } "
                "code { font-family: Consolas, monospace; font-size: 12px; color: #0969DA; }"
            )
            self.text_browser.document().setDefaultStyleSheet(md_css)
            self.text_browser.setMarkdown(text_content)

            # Ensure all markdown link anchors explicitly carry the brand link color
            doc = self.text_browser.document()
            block = doc.begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    fragment = it.fragment()
                    if fragment.isValid():
                        fmt = fragment.charFormat()
                        if fmt.isAnchor():
                            cursor = QTextCursor(doc)
                            cursor.setPosition(fragment.position())
                            cursor.setPosition(
                                fragment.position() + fragment.length(),
                                QTextCursor.MoveMode.KeepAnchor,
                            )
                            fmt.setForeground(link_qcolor)
                            cursor.setCharFormat(fmt)
                    it += 1
                block = block.next()
        else:
            self.text_browser.setHtml(
                format_plain_license(text_content, text_color, is_dark)
            )

        # Bottom Action Bar (Single Close button for clean 2 -> 1 color hierarchy)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()

        self.btn_close = AnimatedButton(
            loc_manager.tr("About.BtnClose", "Close"),
            theme_manager=theme_manager,
        )
        adjust_button_to_text(self.btn_close)
        self.btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self.btn_close)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)
        main_layout.addLayout(header_layout)
        main_layout.addWidget(self.text_browser, stretch=1)
        main_layout.addLayout(bottom_layout)

        if self.btn_open_online:
            self.setTabOrder(self.btn_open_online, self.text_browser)
            self.setTabOrder(self.text_browser, self.btn_close)
            self.setTabOrder(self.btn_close, self.btn_open_online)
        else:
            self.setTabOrder(self.text_browser, self.btn_close)
            self.setTabOrder(self.btn_close, self.text_browser)
        self.btn_close.setFocus()

    @Slot()
    def _on_open_online_clicked(self) -> None:
        if self.online_url:
            webbrowser.open(self.online_url)


LICENSE_METADATA = {
    "ymu-shield": {
        "title": "PolyForm Shield License 1.0.0",
        "files": ["assets/licenses/LICENSE-POLYFORM-SHIELD.md"],
        "url": "https://polyformproject.org/licenses/shield/1.0.0",
        "is_markdown": True,
    },
    "pyside-lgpl": {
        "title": "GNU LGPL v3.0 (PySide6 / Qt6)",
        "files": [
            "assets/licenses/LICENSE-LGPL-3.0.txt",
            "assets/licenses/LGPL-INSTALL.txt",
        ],
        "url": "https://www.qt.io/licensing/",
        "is_markdown": False,
    },
    "rubik-ofl": {
        "title": "SIL Open Font License 1.1 (Rubik)",
        "files": ["assets/licenses/OFL.txt"],
        "url": "https://openfontlicense.org/open-font-license-official-text/",
        "is_markdown": False,
    },
    "lucide-isc": {
        "title": "ISC License (Lucide Icons)",
        "files": ["assets/licenses/LICENSE-ISC.txt"],
        "url": "https://opensource.org/license/isc-license-txt",
        "is_markdown": False,
    },
    "requests-apache": {
        "title": "Apache License 2.0 (requests)",
        "files": ["assets/licenses/LICENSE-APACHE-2.0.txt"],
        "url": "https://www.apache.org/licenses/LICENSE-2.0",
        "is_markdown": False,
    },
    "yimmenu-gpl": {
        "title": "GNU General Public License v2.0 (YimMenu)",
        "files": ["assets/licenses/LICENSE-GPL-2.0.txt"],
        "url": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.html",
        "is_markdown": False,
    },
}


class AboutDialog(QDialog):
    """Modal dialog displaying comprehensive project metadata, runtime environment, credits, and open-source licenses."""

    def __init__(self, theme_manager, loc_manager, parent=None):
        super().__init__(parent)
        self.theme_manager = theme_manager
        self.loc_manager = loc_manager

        # Determine clean version strings
        raw_version = update_checker.LOCAL_VERSION
        clean_version_number = raw_version.removeprefix("v")
        badge_version_text = f"v{clean_version_number}"

        # Dynamic dialog width based on the copyright and license string (measured with 12px label font)
        copyright_text = f"© 2024-2026 NiiV3AU • {loc_manager.tr('About.ShieldNotice', 'Free for non-commercial and permitted use under PolyForm Shield License 1.0.0.')}"
        label_font = QFont(self.font())
        label_font.setPixelSize(12)
        font_metrics = QFontMetrics(label_font)
        copyright_advance = font_metrics.horizontalAdvance(copyright_text)
        # 40px outer margins + 12px header margins + 48px logo + 14px spacing + 40px buffer
        computed_width = copyright_advance + 40 + 12 + 48 + 14 + 40
        initial_width = max(660, min(computed_width, 900))

        # Clamp against screen available geometry to prevent offscreen overflow on high DPI scaling
        screen = self.screen() or QGuiApplication.primaryScreen()
        avail_geo = screen.availableGeometry() if screen else None
        if avail_geo:
            max_width = max(400, avail_geo.width() - 40)
            max_height = max(300, avail_geo.height() - 40)
            target_width = min(initial_width, max_width)
            target_height = min(600, max_height)
            min_width = min(540, target_width)
            min_height = min(360, target_height)
        else:
            target_width = initial_width
            target_height = 600
            min_width = 540
            min_height = 360

        self.setObjectName("AboutDialog")
        self.setWindowTitle(loc_manager.tr("About.Title", "About YMU"))
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.resize(target_width, target_height)
        self.setMinimumSize(min_width, min_height)

        is_dark = theme_manager.current_theme == "dark"
        icon_path = ICON_DARK_PATH if is_dark else ICON_LIGHT_PATH
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        is_rtl = (
            self.isRightToLeft()
            or (parent is not None and parent.isRightToLeft())
            or (theme_manager is not None and getattr(theme_manager, "is_rtl", False))
        )
        if is_rtl:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            font_family = "Rubik, Segoe UI Arabic, Segoe UI, Tahoma, sans-serif"
        else:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            font_family = "Rubik, Segoe UI, Segoe UI Arabic, Yu Gothic UI, Microsoft YaHei UI, Microsoft JhengHei UI, Malgun Gothic, Nirmala UI, Leelawadee UI, Meiryo UI, Meiryo, sans-serif"

        dir_attr = "rtl" if is_rtl else "ltr"
        text_align = "right" if is_rtl else "left"
        text_color = "#E0E0E0" if is_dark else "#121212"
        muted_color = "#8B8B8B" if is_dark else "#555555"
        border_color = "#3A3A3A" if is_dark else "#E0E3E8"

        # --- Header Section ---
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(6, 4, 6, 4)
        header_layout.setSpacing(14)

        logo_label = QLabel()
        if os.path.exists(ICON_SVG_PATH):
            icon_color = QColor("#FFFFFF") if is_dark else QColor("#121212")
            pixmap = create_colored_pixmap(ICON_SVG_PATH, icon_color, QSize(48, 48))
            logo_label.setPixmap(pixmap)
        else:
            icon_path = ICON_DARK_PATH if is_dark else ICON_LIGHT_PATH
            if not os.path.exists(icon_path):
                icon_path = resource_path(os.path.join("assets", "icons", "ymu.ico"))
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                logo_label.setPixmap(
                    pixmap.scaled(
                        48,
                        48,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
        logo_label.setFixedSize(48, 48)
        header_layout.addWidget(logo_label)

        meta_layout = QVBoxLayout()
        meta_layout.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)

        title_label = QLabel("YimMenuUpdater")
        title_label.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {text_color}; font-family: {font_family};"
        )
        title_row.addWidget(title_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Monochromatic subdued version badge (compact)
        version_badge = QLabel(badge_version_text)
        badge_bg = "#383838" if is_dark else "#E6E8EB"
        badge_text_color = "#9E9E9E" if is_dark else "#5B6169"
        badge_border = "#484848" if is_dark else "#D0D4DC"
        version_badge.setStyleSheet(
            f"background-color: {badge_bg}; color: {badge_text_color}; border: 1px solid {badge_border}; "
            f"font-size: 12px; font-weight: 600; padding: 2px 6px; border-radius: 4px; font-family: {font_family};"
        )
        version_badge.setFixedHeight(20)
        version_badge.setContentsMargins(0, 0, 0, 0)
        version_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(version_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        title_row.addStretch()

        link_colors = {
            "color_normal": ("#8B8B8B", "#555555"),
            "color_hover": ("#E0E0E0", "#121212"),
        }
        self.btn_website = StatefulButton(
            f"  {loc_manager.tr('About.BtnWebsite', 'Website')}",
            theme_manager=theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_colors,
        )
        self.btn_website.setObjectName("LinkButton")
        self.btn_website.clicked.connect(self._on_website_clicked)

        self.btn_github = StatefulButton(
            f"  {loc_manager.tr('About.BtnGitHub', 'GitHub')}",
            theme_manager=theme_manager,
            icon_path=resource_path(
                os.path.join("assets", "icons", "external-link.svg")
            ),
            **link_colors,
        )
        self.btn_github.setObjectName("LinkButton")
        self.btn_github.clicked.connect(self._on_github_clicked)

        title_row.addWidget(self.btn_website)
        title_row.addWidget(self.btn_github)

        subtitle_label = QLabel(
            loc_manager.tr(
                "About.Subtitle",
                "The smart launcher for YimMenu: Always updated, always ready.",
            )
        )
        subtitle_label.setTextFormat(Qt.TextFormat.PlainText)
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet(
            f"font-size: 12px; color: {muted_color}; font-family: {font_family};"
        )

        copyright_label = QLabel(copyright_text)
        copyright_label.setTextFormat(Qt.TextFormat.PlainText)
        copyright_label.setWordWrap(True)
        copyright_label.setStyleSheet(
            f"font-size: 12px; color: {muted_color}; font-family: {font_family};"
        )

        if is_rtl:
            subtitle_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            copyright_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        meta_layout.addLayout(title_row)
        meta_layout.addWidget(subtitle_label)
        meta_layout.addWidget(copyright_label)
        header_layout.addLayout(meta_layout)

        # --- Tabs Section ---
        self.tab_bar = QTabBar()
        self.tab_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tab_bar.setExpanding(False)
        self.tab_bar.setUsesScrollButtons(False)
        self.tab_bar.addTab(loc_manager.tr("About.TabGeneral", "General"))
        self.tab_bar.addTab(loc_manager.tr("About.TabLicenses", "Licenses"))
        self.tab_bar.addTab(loc_manager.tr("About.TabCredits", "Credits"))

        centering_layout = QHBoxLayout()
        centering_layout.addStretch()
        centering_layout.addWidget(self.tab_bar)
        centering_layout.addStretch()

        self.content_stack = QStackedWidget()
        self._is_rtl = is_rtl
        self._dir_attr = dir_attr
        self._text_align = text_align
        self._font_family = font_family
        self._text_color = text_color
        self._lrm = "&lrm;" if is_rtl else ""
        self._card_style = f"margin-bottom:10px; padding:12px; border:1px solid {border_color}; border-radius:8px;"

        available_locales = (
            loc_manager.get_available_locales()
            if hasattr(loc_manager, "get_available_locales")
            else []
        )
        lang_count = max(len(available_locales), 16)
        mono_font = "Consolas, monospace"
        lbl_padding = (
            "padding: 4px 0 4px 20px;" if is_rtl else "padding: 4px 20px 4px 0;"
        )
        val_padding = "padding: 4px 0;"

        lrm = self._lrm

        # General Tab HTML
        desc_text = html.escape(
            loc_manager.tr(
                "About.Description",
                "The smart launcher, updater, and injector for YimMenu and YimMenuV2.",
            )
        )
        features_title = html.escape(loc_manager.tr("About.Features", "Key Features"))
        env_title = html.escape(loc_manager.tr("About.Environment", "Environment"))

        env_specs = [
            ("YMU Version", clean_version_number, True),
            (
                "Python Runtime",
                f"{platform.python_version()} ({platform.architecture()[0]})",
                False,
            ),
            ("PySide6 / Qt", f"{PySide6.__version__} (Qt {qVersion()})", False),
            (
                "Operating System",
                f"{platform.system()} {platform.release()} ({platform.version()})",
                False,
            ),
        ]

        if is_rtl:
            table_rows = "".join(
                f"<tr><td dir='rtl' align='right' style='{val_padding} font-family:{mono_font}; font-size:12px; {'font-weight:600; ' if bold else ''}vertical-align:middle;'>{val}&lrm;</td>"
                f"<td dir='rtl' align='right' style='{lbl_padding} color:{muted_color}; width:164px; white-space:nowrap; vertical-align:middle;'>{lbl}:&lrm;</td></tr>"
                for lbl, val, bold in env_specs
            )
        else:
            table_rows = "".join(
                f"<tr><td dir='ltr' align='left' style='{lbl_padding} color:{muted_color}; width:164px; white-space:nowrap; vertical-align:middle;'>{lbl}:</td>"
                f"<td dir='ltr' align='left' style='{val_padding} font-family:{mono_font}; font-size:12px; {'font-weight:600; ' if bold else ''}vertical-align:middle;'>{val}</td></tr>"
                for lbl, val, bold in env_specs
            )

        general_html = f"""
        <html dir='{dir_attr}'>
        <body dir='{dir_attr}' align='{text_align}' style='font-family:{font_family}; color:{text_color}; font-size:14px; line-height:140%;'>
          <p dir='{dir_attr}' align='{text_align}' style='margin:0 0 10px 0;'>
            {desc_text}
          </p>
          <p dir='{dir_attr}' align='{text_align}' style='margin:0 0 6px 0; font-weight:700; color:{text_color}; font-size:14px;'>
            {features_title}
          </p>
          <ul dir='{dir_attr}' align='{text_align}' style='margin:0 0 12px 0; padding-{("right" if is_rtl else "left")}:20px;'>
            <li dir='{dir_attr}' align='{text_align}'>{lrm}{loc_manager.tr("About.FeatureDualEdition", "<b>Dual-Edition Support:</b> Seamless switching between GTA V Legacy (YimMenu) and Enhanced (YimMenuV2) with independent settings.")}{lrm}</li>
            <li dir='{dir_attr}' align='{text_align}'>{lrm}{loc_manager.tr("About.FeatureAutoUpdates", "<b>Automated DLL Management:</b> Automatic update checks on startup, one-click downloads, and SHA-256 integrity verification.")}{lrm}</li>
            <li dir='{dir_attr}' align='{text_align}'>{lrm}{loc_manager.tr("About.FeatureSafeInjection", "<b>Native Injection Engine:</b> Safe Win32 DLL injection with BattlEye detection and in-memory verification.")}{lrm}</li>
            <li dir='{dir_attr}' align='{text_align}'>{lrm}{loc_manager.tr("About.FeatureLuaManagement", "<b>Lua Script Manager:</b> Direct script discovery, safe-mode bulk actions, and instant folder access.")}{lrm}</li>
            <li dir='{dir_attr}' align='{text_align}'>{lrm}{loc_manager.tr("About.FeatureAccessibility", "<b>Modern UI/UX:</b> Adaptive Dark/Light themes, full RTL layout support, and {0} localizations.").format(lang_count)}{lrm}</li>
          </ul>
          <p dir='{dir_attr}' align='{text_align}' style='margin:0 0 6px 0; font-weight:700; color:{text_color}; font-size:14px;'>
            {env_title}
          </p>
          <table dir='{dir_attr}' align='{text_align}' style='width:100%; border-collapse:collapse; font-size:12px; color:{text_color};'>
            {table_rows}
          </table>
        </body>
        </html>
        """

        card_style = self._card_style

        # Credits Tab HTML
        credits_html = f"""
        <html dir='{dir_attr}'>
        <body dir='{dir_attr}' align='{text_align}' style='font-family:{font_family}; color:{text_color}; font-size:14px; line-height:150%;'>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>{loc_manager.tr("About.CreditsLeadTitle", "Lead Developer & Architecture")}</b><br>
            <b>NiiV3AU</b>: {loc_manager.tr("About.CreditsLeadDesc", "Creator and maintainer of YimMenuUpdater (YMU).")}{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>{loc_manager.tr("About.CreditsModTitle", "Mod Menu Development")}</b><br>
            <b>YimMenu Team & Contributors</b>: {loc_manager.tr("About.CreditsModDesc", "Development and maintenance of the open-source YimMenu (Legacy) and YimMenuV2 (Enhanced Edition) mod menus.")}{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>{loc_manager.tr("About.CreditsSaveTitle", "Local Saves")}</b><br>
            <b>FSL</b>: {loc_manager.tr("About.CreditsSaveDesc", "UnknownCheats community contributors for the local GTA Online save redirection tool.")}{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>{loc_manager.tr("About.CreditsTestTitle", "Community & Beta Testers")}</b><br>
            {loc_manager.tr("About.CreditsTestDesc", "Special thanks to all community members and beta testers who tested pre-release builds, verified bug fixes, and suggested improvements across game updates.")}{lrm}
          </div>
        </body>
        </html>
        """

        self.content_stack.addWidget(self._build_scrollable_page(general_html))
        self.content_stack.addWidget(
            self._build_scrollable_page(
                self._build_licenses_html, on_link_activated=self._handle_license_click
            )
        )
        self.content_stack.addWidget(self._build_scrollable_page(credits_html))

        self.tab_bar.currentChanged.connect(self.content_stack.setCurrentIndex)
        if self.tab_bar.count() > 0:
            self.content_stack.setCurrentIndex(0)

        # --- Bottom Close Button ---
        self.btn_close = AnimatedButton(
            loc_manager.tr("About.BtnClose", "Close"),
            theme_manager=theme_manager,
        )
        adjust_button_to_text(self.btn_close)
        self.btn_close.clicked.connect(self.accept)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.btn_close)

        # Main Layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(12)
        main_layout.addLayout(header_layout)
        main_layout.addLayout(centering_layout)
        main_layout.addWidget(self.content_stack, stretch=1)
        main_layout.addLayout(bottom_layout)

        # Focus & Tab Chain
        self.setTabOrder(self.tab_bar, self.btn_website)
        self.setTabOrder(self.btn_website, self.btn_github)
        self.setTabOrder(self.btn_github, self.btn_close)
        self.setTabOrder(self.btn_close, self.tab_bar)

    @Slot(str)
    def _handle_license_click(self, url: str) -> None:
        online_url, _, key = url.partition("#")
        meta = LICENSE_METADATA.get(key)
        if meta:
            parts: list[str] = []
            files = meta.get("files")
            if isinstance(files, list):
                for rel_path in files:
                    abs_path = resource_path(rel_path)
                    if (
                        not os.path.exists(abs_path)
                        and rel_path == "assets/licenses/LICENSE-POLYFORM-SHIELD.md"
                    ):
                        abs_path = resource_path("LICENSE.md")
                    if (
                        not os.path.exists(abs_path)
                        and rel_path == "assets/licenses/OFL.txt"
                    ):
                        abs_path = resource_path("assets/fonts/OFL.txt")
                    if os.path.exists(abs_path):
                        try:
                            with open(abs_path, encoding="utf-8") as f:
                                text = f.read().strip("\r\n")
                                if text:
                                    parts.append(text)
                        except Exception:
                            pass
            if parts:
                divider = "\n\n" + ("=" * 60) + "\n\n"
                content = divider.join(parts)
                is_md = bool(meta.get("is_markdown", False))
                dlg = LicenseViewerDialog(
                    title=str(meta.get("title", "License")),
                    text_content=content,
                    online_url=str(meta.get("url", "")) if meta.get("url") else None,
                    theme_manager=self.theme_manager,
                    loc_manager=self.loc_manager,
                    is_markdown=is_md,
                    parent=self,
                )
                dlg.exec()
                return

        target = online_url or url
        if target:
            webbrowser.open(target)

    def _build_scrollable_page(
        self,
        html_or_builder: str | Callable[[str], str],
        on_link_activated: Callable[[str], None] | None = None,
    ) -> QScrollArea:
        is_rtl = self._is_rtl
        text_color = self._text_color
        if callable(html_or_builder):
            label = HoverableRichLabel(
                html_or_builder,
                is_rtl=is_rtl,
                text_color=text_color,
                on_link_activated=on_link_activated,
            )
        else:
            label = QLabel(html_or_builder)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setWordWrap(True)
            if on_link_activated:
                label.setOpenExternalLinks(False)
                label.linkActivated.connect(on_link_activated)
            else:
                label.setOpenExternalLinks(True)
            label.setLayoutDirection(
                Qt.LayoutDirection.RightToLeft
                if is_rtl
                else Qt.LayoutDirection.LeftToRight
            )
            label.setAlignment(
                (Qt.AlignmentFlag.AlignRight if is_rtl else Qt.AlignmentFlag.AlignLeft)
                | Qt.AlignmentFlag.AlignTop
            )
            label.setStyleSheet(f"color: {text_color}; background: transparent;")

        container = QWidget()
        container.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl else Qt.LayoutDirection.LeftToRight
        )
        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.addWidget(label)
        layout.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_area.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl else Qt.LayoutDirection.LeftToRight
        )
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("background: transparent;")
        scroll_area.setWidget(container)
        return scroll_area

    @staticmethod
    def _license_link(
        url: str, key: str, hovered_link: str, text: str | None = None
    ) -> str:
        label = text or url
        href = f"{url}#{key}"
        is_hovered = hovered_link in (href, key)
        dec = "underline" if is_hovered else "none"
        return f"<a href='{href}' style='color:#28A745; text-decoration:{dec};'>{label}</a>"

    def _build_licenses_html(self, hovered_link: str = "") -> str:
        dir_attr = self._dir_attr
        text_align = self._text_align
        font_family = self._font_family
        text_color = self._text_color
        lrm = self._lrm
        card_style = self._card_style
        link = self._license_link
        return f"""
        <html dir='{dir_attr}'>
        <body dir='{dir_attr}' align='{text_align}' style='font-family:{font_family}; color:{text_color}; font-size:14px; line-height:150%;'>
          <p dir='{dir_attr}' align='{text_align}' style='margin:0 0 12px 0;'>
            {self.loc_manager.tr("About.LicensesNotice", "YimMenuUpdater is source-available software built upon free and open-source libraries. We gratefully acknowledge the following projects:")}{lrm}
          </p>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>YimMenuUpdater (YMU)</b><br>
            License: {link("https://polyformproject.org/licenses/shield/1.0.0", "ymu-shield", hovered_link, "PolyForm Shield License 1.0.0")}{lrm}<br>
            Copyright: © 2024-2026 NiiV3AU. Free for non-commercial and permitted use.{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>PySide6 / Qt6</b> (Official Python GUI Framework)<br>
            License: {link("https://www.qt.io/licensing/", "pyside-lgpl", hovered_link, "GNU LGPL v3.0")}{lrm}<br>
            Copyright: © The Qt Company Ltd. and other contributors.{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>Rubik Typeface</b> (UI Typography)<br>
            License: {link("https://openfontlicense.org/open-font-license-official-text/", "rubik-ofl", hovered_link, "SIL Open Font License 1.1 (OFL)")}{lrm}<br>
            Copyright: © 2015 The Rubik Project Authors (Hubert & Fischer, Meir Sadan).{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>Lucide Icons</b> (Application Icons)<br>
            License: {link("https://opensource.org/license/isc-license-txt", "lucide-isc", hovered_link, "ISC License")}{lrm}<br>
            Copyright: © Cole Bemis, Lucide Contributors.{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>requests</b> (HTTP Networking Client)<br>
            License: {link("https://www.apache.org/licenses/LICENSE-2.0", "requests-apache", hovered_link, "Apache License 2.0")}{lrm}<br>
            Copyright: © Kenneth Reitz.{lrm}
          </div>
          <div dir='{dir_attr}' align='{text_align}' style='{card_style}'>
            <b>YimMenu & YimMenuV2</b> (Grand Theft Auto V Mod Menus)<br>
            License: {link("https://www.gnu.org/licenses/old-licenses/gpl-2.0.html", "yimmenu-gpl", hovered_link, "GNU General Public License v2.0 (GPLv2)")}{lrm}<br>
            Copyright: © YimMenu Development Team.{lrm}
          </div>
        </body>
        </html>
        """

    @Slot()
    def _on_website_clicked(self) -> None:
        webbrowser.open("https://ymu.pages.dev/")

    @Slot()
    def _on_github_clicked(self) -> None:
        webbrowser.open("https://github.com/NiiV3AU/YMU")
