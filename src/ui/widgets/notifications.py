# notifications.py - In-app animated notification system.
import logging
import os
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPoint,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.paths import resource_path
from ui.utils import create_colored_icon
from ui.widgets.buttons import StatefulButton

if TYPE_CHECKING:
    from ui.styles.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class NotificationWidget(QFrame):
    """A single, animated notification widget in the style of a 'card'."""

    closed = Signal()

    def __init__(
        self,
        title: str,
        message: str,
        theme_manager: "ThemeManager",
        icon_type: str = "info",
        parent: QWidget | None = None,
        action_text: str | None = None,
        action_callback=None,
        tag: str | None = None,
    ):
        super().__init__(parent)
        self.setObjectName("NotificationCard")
        self.theme_manager = theme_manager

        self.title = title
        self.message = message
        self.tag = tag
        self.icon_type = icon_type

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(15, 12, 15, 12)
        main_layout.setSpacing(15)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinAndMaxSize)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        main_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._set_icon(icon_type)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("NotificationTitle")

        self.message_label = QLabel(message)
        self.message_label.setObjectName("NotificationMessage")
        self.message_label.setWordWrap(True)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)

        if action_text and action_callback:
            self.action_btn = QPushButton(action_text)
            self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.action_btn.setMinimumWidth(100)
            self.action_btn.setStyleSheet(
                """
                QPushButton {
                    background-color: #333333;
                    color: #FFFFFF;
                    border: 1px solid #555555;
                    border-radius: 4px;
                    padding: 4px 12px; 
                    font-size: 11px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #28A745;
                    border-color: #28A745;
                }
            """
            )
            self.action_btn.clicked.connect(action_callback)
            self.action_btn.clicked.connect(self.close_animation)
            text_layout.addSpacing(5)
            text_layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignLeft)

        main_layout.addLayout(text_layout)

        top_right_layout = QVBoxLayout()
        self.close_button = StatefulButton(
            "",
            theme_manager=self.theme_manager,
            icon_path=resource_path(os.path.join("assets", "icons", "x.svg")),
            color_normal=("#8B8B8B", "#AAAAAA"),
            color_hover=("#E0E0E0", "#121212"),
        )
        self.close_button.setObjectName("NotificationCloseButton")
        self.close_button.setFixedSize(24, 24)
        self.close_button.setIconSize(QSize(20, 20))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.clicked.connect(self.close_animation)

        top_right_layout.addWidget(
            self.close_button,
            0,
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )
        top_right_layout.addStretch()
        main_layout.addLayout(top_right_layout)

        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self.current_animation = None

    def _set_icon(self, icon_type: str):
        icons = {
            "success": os.path.join("assets", "icons", "check-circle.svg"),
            "error": os.path.join("assets", "icons", "alert-triangle.svg"),
            "info": os.path.join("assets", "icons", "info.svg"),
        }
        icon_path = resource_path(icons.get(icon_type, icons["info"]))
        is_light = self.theme_manager.current_theme == "light"
        color_map = {
            "success": QColor("#28A745"),
            "error": QColor("#e84555"),
            "info": QColor("#555555") if is_light else QColor("#8B8B8B"),
        }
        icon = create_colored_icon(
            icon_path, color_map.get(icon_type, color_map["info"])
        )
        self.icon_label.setPixmap(icon.pixmap(32, 32))

    def enterEvent(self, event):
        self._close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self._close_timer.interval() > 0:
            self._close_timer.start()
        super().leaveEvent(event)

    def start_fly_in(self, target_pos: QPoint, duration: int):
        parent = self.parentWidget()
        if not parent:
            return

        start_pos = QPoint(parent.width(), target_pos.y())
        self.move(start_pos)
        self.animate_to(target_pos)

        if duration > 0:
            self._close_timer.setInterval(duration)
            self._close_timer.timeout.connect(self.close_animation)
            self._close_timer.start()

    def update_content(
        self,
        title: str,
        message: str,
        icon_type: str = "info",
        duration: int = 6000,
        action_text: str | None = None,
        action_callback=None,
    ):
        """Updates an existing notification's content in place and resets its close timer."""
        self.title = title
        self.message = message
        self.title_label.setText(title)
        self.message_label.setText(message)
        self._set_icon(icon_type)

        if action_text and hasattr(self, "action_btn"):
            self.action_btn.setText(action_text)
            if action_callback:
                try:
                    self.action_btn.clicked.disconnect()
                except RuntimeError:
                    pass
                self.action_btn.clicked.connect(action_callback)
                self.action_btn.clicked.connect(self.close_animation)

        if duration > 0:
            self._close_timer.stop()
            self._close_timer.setInterval(duration)
            self._close_timer.start()

        self.adjustSize()

    def close_animation(self):
        self._close_timer.stop()
        parent = self.parentWidget()
        if not parent:
            self._on_animation_finished()
            return

        end_pos = QPoint(self.pos().x(), parent.height())
        self.animate_to(end_pos, finished_slot=self._on_animation_finished)

    def animate_to(self, target_pos: QPoint, finished_slot=None):
        """A generic animation method to move the widget."""
        self.current_animation = QPropertyAnimation(self, b"pos")
        self.current_animation.setDuration(350)
        self.current_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.current_animation.setEndValue(target_pos)
        if finished_slot:
            self.current_animation.finished.connect(finished_slot)
        self.current_animation.start()

    def _on_animation_finished(self):
        self.closed.emit()
        self.deleteLater()


class NotificationManager(QObject):
    """Manages the creation, positioning, and lifecycle of notifications."""

    def __init__(self, parent: QWidget, theme_manager: "ThemeManager"):
        super().__init__(parent)
        self.parent_widget = parent
        self.theme_manager = theme_manager
        self.notifications: list[NotificationWidget] = []
        self.padding = 16
        self.gap = 8

    def show(
        self,
        title: str,
        message: str,
        icon_type: str = "info",
        duration: int = 6000,
        action_text: str | None = None,
        action_callback=None,
        tag: str | None = None,
    ):
        # If a tag is specified, update an existing notification with that tag in place
        if tag is not None:
            for n in self.notifications:
                if getattr(n, "tag", None) == tag:
                    n.update_content(
                        title=title,
                        message=message,
                        icon_type=icon_type,
                        duration=duration,
                        action_text=action_text,
                        action_callback=action_callback,
                    )
                    self._reposition_notifications()
                    return
        else:
            for n in self.notifications:
                if n.title == title and n.message == message:
                    logger.info(f"Suppressed duplicate notification: '{title}'")
                    return

        notification = NotificationWidget(
            title=title,
            message=message,
            theme_manager=self.theme_manager,
            icon_type=icon_type,
            parent=self.parent_widget,
            action_text=action_text,
            action_callback=action_callback,
            tag=tag,
        )
        notification.show()
        notification.closed.connect(lambda: self._remove_notification(notification))

        self.notifications.append(notification)
        self._reposition_notifications(is_new=True, new_duration=duration)

    def _reposition_notifications(self, is_new: bool = False, new_duration: int = 0):
        """Calculates positions for all notifications and triggers their animations."""
        parent_width = self.parent_widget.width()
        parent_height = self.parent_widget.height()
        current_y = parent_height - self.padding

        for notification in reversed(self.notifications):
            notification.adjustSize()
            h = notification.height()
            current_y -= h
            pos_x = parent_width - notification.width() - self.padding
            target_pos = QPoint(pos_x, current_y)
            is_the_very_newest = is_new and notification is self.notifications[-1]
            if is_the_very_newest:
                notification.start_fly_in(target_pos, new_duration)
            elif notification.pos() != target_pos:
                notification.animate_to(target_pos)
            current_y -= self.gap

    def _remove_notification(self, notification: NotificationWidget):
        if notification in self.notifications:
            self.notifications.remove(notification)
        self._reposition_notifications()
