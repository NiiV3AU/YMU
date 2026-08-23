# dialogs.py - Reusable modal dialogs.
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLayout,
    QStackedWidget,
    QTabBar,
    QVBoxLayout,
)


class InfoDialog(QDialog):
    """A reusable, modal dialog for showing information in tabs with dynamic resizing."""

    def __init__(self, title: str, content: dict, theme_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("InfoDialog")
        self.setModal(True)

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
        text_color = "#E0E0E0" if is_dark else "#121212"
        font_family = "Manrope, Segoe UI, Meiryo, Microsoft YaHei, sans-serif"

        for tab_title, tab_content in content.items():
            self.tab_bar.addTab(tab_title)
            formatted_content = tab_content.replace("\n", "<br>")
            html_text = (
                f"<html><body>"
                f"<div align='center' style='font-family:{font_family}; font-size:14px; color:{text_color};'>"
                f"{formatted_content}"
                f"</div></body></html>"
            )

            content_label = QLabel(html_text)
            content_label.setTextFormat(Qt.TextFormat.RichText)
            content_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_label.setWordWrap(True)
            content_label.setOpenExternalLinks(True)
            content_label.setContentsMargins(10, 20, 10, 20)

            self.content_stack.addWidget(content_label)

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

    def _on_tab_changed(self, index):
        self.content_stack.setCurrentIndex(index)
        QApplication.processEvents()
        self.adjustSize()
