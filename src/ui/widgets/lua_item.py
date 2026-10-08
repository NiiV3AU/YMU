# lua_item.py - Custom row widget for Lua scripts with hover action button.
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QCursor, QEnterEvent, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidgetItem, QWidget

from core.paths import resource_path
from ui.widgets.buttons import StatefulButton

if TYPE_CHECKING:
    from ui.styles.theme_manager import ThemeManager


class LuaScriptItemWidget(QWidget):
    """Row widget for a Lua script item displaying the script name and a hover
    caret button to transfer the script between enabled and disabled states.
    """

    actionClicked = Signal(str)

    def __init__(
        self,
        script_name: str,
        direction: str,  # "enable" or "disable"
        theme_manager: "ThemeManager",
        parent: QWidget | None = None,
        item: QListWidgetItem | None = None,
        is_rtl: bool = False,
        tooltip: str | None = None,
    ):
        super().__init__(parent)
        self.script_name = script_name
        self.direction = direction
        self.theme_manager = theme_manager
        self.item = item

        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if is_rtl else Qt.LayoutDirection.LeftToRight
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)

        self.label = QLabel(script_name)
        self.label.setObjectName("LuaScriptLabel")
        self.label.setAlignment(
            (Qt.AlignmentFlag.AlignRight if is_rtl else Qt.AlignmentFlag.AlignLeft)
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Direction determines caret icon:
        # In LTR: "enable" points right (-> enabled), "disable" points left (<- disabled).
        # In RTL: "enable" points left (<- enabled), "disable" points right (-> disabled).
        if direction == "enable":
            icon_file = "chevron-left.svg" if is_rtl else "chevron-right.svg"
            color_normal = ("#28A745", "#28A745")
            color_hover = ("#34D399", "#218838")
            btn_tooltip = tooltip or "Enable script"
        else:
            icon_file = "chevron-right.svg" if is_rtl else "chevron-left.svg"
            color_normal = ("#e84555", "#dc3545")
            color_hover = ("#ff6b7a", "#c82333")
            btn_tooltip = tooltip or "Disable script"

        self.action_btn = StatefulButton(
            "",
            theme_manager=theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", icon_file)),
            color_normal=color_normal,
            color_hover=color_hover,
        )
        self.action_btn.setObjectName("LuaItemActionButton")
        self.action_btn.setFixedSize(22, 22)
        self.action_btn.setIconSize(QSize(14, 14))
        self.action_btn.setToolTip(btn_tooltip)
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.hide()
        self.action_btn.installEventFilter(self)

        self.action_btn.clicked.connect(
            lambda: self.actionClicked.emit(self.script_name)
        )

        layout.addWidget(self.label, stretch=1)
        layout.addWidget(
            self.action_btn,
            alignment=Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter,
        )

    def enterEvent(self, event: QEnterEvent):
        super().enterEvent(event)
        self.action_btn.show()

    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)
        pos = self.mapFromGlobal(QCursor.pos())
        if not self.rect().contains(pos):
            self.action_btn.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched == self.action_btn and event.type() == QEvent.Type.Leave:
            pos = self.mapFromGlobal(QCursor.pos())
            if not self.rect().contains(pos):
                self.action_btn.hide()
        return super().eventFilter(watched, event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.item:
            try:
                lw = self.item.listWidget()
                if lw:
                    if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                        self.item.setSelected(not self.item.isSelected())
                    else:
                        lw.setCurrentItem(self.item)
                        self.item.setSelected(True)
            except RuntimeError:
                pass
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.actionClicked.emit(self.script_name)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
