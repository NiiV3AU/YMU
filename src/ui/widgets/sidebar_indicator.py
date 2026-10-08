# sidebar_indicator.py - Animated sliding indicator pill for the sidebar.
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRectF,
    Qt,
)
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QWidget

if TYPE_CHECKING:
    from ui.styles.theme_manager import ThemeManager


class SidebarIndicator(QWidget):
    """An animated pill-shaped indicator that slides along the Y-axis to highlight
    the currently active sidebar navigation button.

    Renders a subtle background capsule and a bright green accent pill on the
    leading edge (respecting LTR/RTL layout direction).
    """

    def __init__(
        self,
        parent: QWidget,
        theme_manager: "ThemeManager",
        duration: int = 240,
        easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    ):
        super().__init__(parent)
        self.setObjectName("SidebarIndicator")
        self.theme_manager = theme_manager
        self._duration = duration
        self._easing_curve = easing_curve
        self._current_button: QAbstractButton | None = None

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(self._duration)
        self._anim.setEasingCurve(self._easing_curve)

        self.theme_manager.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: str):
        self.update()

    def is_animating(self) -> bool:
        return self._anim.state() == QPropertyAnimation.State.Running

    def current_button(self) -> QAbstractButton | None:
        return self._current_button

    def move_to_button(self, button: QAbstractButton | None, animate: bool = True):
        """Animates or instantly snaps the indicator to the target button's geometry."""
        if not button:
            return

        self._current_button = button
        geom = button.geometry()

        # Match size of target button
        self.resize(geom.size())

        target_pos = geom.topLeft()
        if not animate or not self.isVisible() or self.pos() == target_pos:
            self._anim.stop()
            self.move(target_pos)
            return

        self._anim.stop()
        self._anim.setStartValue(self.pos())
        self._anim.setEndValue(target_pos)
        self._anim.start()

    def sync_to_current(self):
        """Immediately snaps to the current button without animation."""
        if self._current_button:
            self.move_to_button(self._current_button, animate=False)

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_dark = self.theme_manager.current_theme == "dark"
        bg_color = QColor("#333333") if is_dark else QColor("#E2E5EA")

        # Capsule background
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 10, 10)

        # Leading green accent pill
        painter.setBrush(QColor("#28A745"))
        bar_w = 4.0
        bar_h = 24.0
        bar_y = (self.height() - bar_h) / 2.0
        is_rtl = self.isRightToLeft()
        bar_x = float(self.width() - bar_w - 4.0) if is_rtl else 4.0

        painter.drawRoundedRect(QRectF(bar_x, bar_y, bar_w, bar_h), 2.0, 2.0)
