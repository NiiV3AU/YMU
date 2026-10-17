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
    Slot,
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

    closed = Signal(object)

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
        self.is_closing = False

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(16)
        main_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.setMaximumWidth(430)

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(32, 32)
        main_layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self._set_icon(icon_type)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        self.title_label = QLabel(title, self)
        self.title_label.setObjectName("NotificationTitle")
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setContentsMargins(2, 0, 2, 0)

        self.message_label = QLabel(message, self)
        self.message_label.setObjectName("NotificationMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label.setMinimumWidth(180)
        self.message_label.setContentsMargins(2, 0, 2, 0)

        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)

        self.action_btn = QPushButton(self)
        self.action_btn.setObjectName("NotificationActionButton")
        self.action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_btn.setMinimumWidth(100)
        self.action_btn.setVisible(False)
        self._action_callback = None
        self.action_btn.clicked.connect(self._on_action_btn_clicked)
        text_layout.addSpacing(6)
        text_layout.addWidget(self.action_btn, 0, Qt.AlignmentFlag.AlignLeading)

        main_layout.addLayout(text_layout)
        self._setup_action(action_text, action_callback)

        top_right_layout = QVBoxLayout()
        top_right_layout.setContentsMargins(0, 4, 0, 0)
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
        self._close_timer.timeout.connect(self.close_animation)

        self._pending_finished_slot = None
        self.current_animation = QPropertyAnimation(self, b"pos", self)
        self.current_animation.setDuration(350)
        self.current_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.current_animation.finished.connect(self._on_pos_animation_finished)

    def _set_icon(self, icon_type: str):
        icons = {
            "success": os.path.join("assets", "icons", "circle-check.svg"),
            "error": os.path.join("assets", "icons", "triangle-alert.svg"),
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

        is_rtl = (
            parent.layoutDirection() == Qt.LayoutDirection.RightToLeft
            or self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        )
        if is_rtl:
            start_pos = QPoint(-self.width(), target_pos.y())
        else:
            start_pos = QPoint(parent.width(), target_pos.y())
        self.move(start_pos)
        self.show()
        self.animate_to(target_pos)

        if duration > 0:
            self._close_timer.setInterval(duration)
            self._close_timer.start()

    def _setup_action(self, action_text: str | None, action_callback=None):
        if action_text and action_callback:
            self._action_callback = action_callback
            self.action_btn.setText(action_text)
            self.action_btn.setVisible(True)
        else:
            self._action_callback = None
            self.action_btn.setVisible(False)

    @Slot()
    def _on_action_btn_clicked(self) -> None:
        cb = self._action_callback
        if callable(cb):
            cb()
        self.close_animation()

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
        self._setup_action(action_text, action_callback)

        if duration > 0:
            self._close_timer.stop()
            self._close_timer.setInterval(duration)
            self._close_timer.start()

    @Slot()
    def close_animation(self):
        if self.is_closing:
            return
        self.is_closing = True
        self._close_timer.stop()
        parent = self.parentWidget()
        if not parent:
            self._on_animation_finished()
            return

        end_pos = QPoint(self.pos().x(), parent.height())
        self.animate_to(end_pos, finished_slot=self._on_animation_finished)

    def animate_to(self, target_pos: QPoint, finished_slot=None):
        """A generic animation method to move the widget."""
        if self.current_animation.state() == QPropertyAnimation.State.Running:
            self._pending_finished_slot = None
            self.current_animation.stop()
        self._pending_finished_slot = finished_slot
        self.current_animation.setStartValue(self.pos())
        self.current_animation.setEndValue(target_pos)
        self.current_animation.start()

    @Slot()
    def _on_pos_animation_finished(self) -> None:
        slot = self._pending_finished_slot
        self._pending_finished_slot = None
        if callable(slot):
            slot()

    @Slot()
    def _on_animation_finished(self):
        self.closed.emit(self)
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
        # Limit active notifications to 4 to prevent overflow off screen
        active = [n for n in self.notifications if not getattr(n, "is_closing", False)]
        if len(active) >= 4:
            active[0].close_animation()

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
                if n.title == title and n.message == message and not n.is_closing:
                    logger.info(f"Suppressed duplicate notification: '{title}'")
                    return

        active_existing = [n for n in self.notifications if not n.is_closing]
        if len(active_existing) >= 3:
            active_existing[0].close_animation()

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
        notification.closed.connect(self._remove_notification)

        self.notifications.append(notification)
        self.reposition_notifications(is_new=True, new_duration=duration)

    def reposition_notifications(self, is_new: bool = False, new_duration: int = 0):
        """Calculates positions for all active notifications and triggers their animations."""
        if not self.parent_widget or not self.parent_widget.isVisible():
            return
        parent_width = self.parent_widget.width()
        parent_height = self.parent_widget.height()
        if parent_height <= 0 or parent_width <= 0:
            return
        current_y = parent_height - self.padding

        active_notifications = [
            n for n in self.notifications if not getattr(n, "is_closing", False)
        ]

        is_rtl = (
            self.parent_widget.layoutDirection() == Qt.LayoutDirection.RightToLeft
            or self.parent_widget.isRightToLeft()
        )

        for notification in reversed(active_notifications):
            notification.adjustSize()
            h = notification.height()
            current_y -= h
            if current_y < self.padding:
                notification.close_animation()
                continue
            if is_rtl:
                pos_x = self.padding
            else:
                pos_x = parent_width - notification.width() - self.padding
            target_pos = QPoint(pos_x, current_y)
            is_the_very_newest = is_new and notification is active_notifications[-1]
            if is_the_very_newest:
                notification.start_fly_in(target_pos, new_duration)
            else:
                if not notification.isVisible():
                    notification.show()
                if notification.pos() != target_pos:
                    notification.animate_to(target_pos)
            current_y -= self.gap

    @Slot(object)
    def _remove_notification(self, notification: NotificationWidget):
        if notification in self.notifications:
            self.notifications.remove(notification)
        self.reposition_notifications()

    # Backward compatibility alias
    _reposition_notifications = reposition_notifications
