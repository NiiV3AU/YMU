# buttons.py - Stateful and animated UI buttons.
from typing import TYPE_CHECKING

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QLinearGradient,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QPushButton

from ui.utils import create_colored_icon

if TYPE_CHECKING:
    from theme_manager import ThemeManager


class StatefulButton(QPushButton):
    """A button that receives its icon colors as tuples (dark, light) and reacts to a signal from the ThemeManager."""

    def __init__(
        self,
        *args,
        theme_manager: "ThemeManager",
        icon_path=None,
        color_normal: tuple | None = None,
        color_hover: tuple | None = None,
        color_checked: tuple | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.theme_manager = theme_manager
        self.icon_path = icon_path

        self.color_tuples = {
            "normal": color_normal,
            "hover": color_hover,
            "checked": color_checked,
        }

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_manager.themeChanged.connect(self.updateThemeColors)
        self.updateThemeColors(self.theme_manager.current_theme)

    def updateThemeColors(self, theme: str):
        """Selects the correct colors from the tuples and recreates the icons."""
        if not self.icon_path:
            return

        idx = 1 if theme == "light" else 0

        c_normal = (
            self.color_tuples["normal"][idx] if self.color_tuples["normal"] else None
        )
        c_hover = (
            self.color_tuples["hover"][idx] if self.color_tuples["hover"] else c_normal
        )
        c_checked = (
            self.color_tuples["checked"][idx]
            if self.color_tuples["checked"]
            else c_hover
        )

        if not c_normal:
            return

        self._icon_normal = create_colored_icon(self.icon_path, QColor(c_normal))
        self._icon_hover = create_colored_icon(self.icon_path, QColor(c_hover))
        self._icon_checked = create_colored_icon(self.icon_path, QColor(c_checked))

        self.updateIcon()

    def updateIcon(self):
        if not hasattr(self, "_icon_normal"):
            return
        if self.isChecked():
            self.setIcon(self._icon_checked)
        elif self.underMouse():
            self.setIcon(self._icon_hover)
        else:
            self.setIcon(self._icon_normal)

    def enterEvent(self, event: QEnterEvent):
        super().enterEvent(event)
        self.updateIcon()

    def leaveEvent(self, event: QEvent):
        super().leaveEvent(event)
        self.updateIcon()

    def setChecked(self, checked):
        super().setChecked(checked)
        self.updateIcon()


class AnimatedButton(StatefulButton):
    """A QPushButton that can play a 'shimmer' animation over itself."""

    _offset_changed = Signal()
    _progress_changed = Signal(float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._progress = 0.0
        self._offset = -0.5
        self._is_animating = False
        self._shimmer_base_color = QColor(255, 255, 255)
        self.current_animation = None

        self.progress_animation = QPropertyAnimation(self, b"progress")
        self.progress_animation.setDuration(200)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def updateThemeColors(self, theme: str):
        """Sets the appropriate shimmer color based on the current theme."""
        if theme == "light":
            self._shimmer_base_color = QColor(0, 0, 0)
        else:
            self._shimmer_base_color = QColor(255, 255, 255)

        super().updateThemeColors(theme)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        radius = 8 if not self.text() else 10
        path.addRoundedRect(self.rect(), radius, radius)
        painter.setClipPath(path)

        if self._progress > 0:
            fill_color = QColor("#28A745")
            fill_color.setAlphaF(0.3)
            fill_width = self.width() * self._progress
            fill_rect = QRectF(0, 0, fill_width, self.height())
            painter.setBrush(fill_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(fill_rect)

        if self._is_animating:
            painter.save()
            shimmer_width = self.width()
            x_pos = self.width() * self._offset - (shimmer_width / 2)
            shimmer_rect = QRectF(x_pos, 0, shimmer_width, self.height())
            gradient = QLinearGradient(shimmer_rect.topLeft(), shimmer_rect.topRight())
            base_color = self._shimmer_base_color
            c_transparent = QColor(base_color)
            c_transparent.setAlpha(0)
            c_edge_glow = QColor(base_color)
            c_edge_glow.setAlpha(
                30 if self.theme_manager.current_theme == "light" else 25
            )
            c_center_glow = QColor(base_color)
            c_center_glow.setAlpha(
                60 if self.theme_manager.current_theme == "light" else 50
            )
            gradient.setColorAt(0.0, c_transparent)
            gradient.setColorAt(0.33, c_edge_glow)
            gradient.setColorAt(0.5, c_center_glow)
            gradient.setColorAt(0.66, c_edge_glow)
            gradient.setColorAt(1.0, c_transparent)
            painter.shear(-0.2, 0)
            painter.setBrush(gradient)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(shimmer_rect)
            painter.restore()

    def _get_progress(self) -> float:
        return self._progress

    def _set_progress(self, value: float):
        self._progress = value
        self._progress_changed.emit(value)
        self.update()

    progress = Property(float, _get_progress, _set_progress, notify=_progress_changed)

    def set_progress(self, value: float):
        """Animates the progress bar to the target value."""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()

        self.progress_animation.setStartValue(self.progress)
        self.progress_animation.setEndValue(value)
        self.progress_animation.start()

    def reset_progress(self):
        """Resets the progress bar instantly to 0."""
        if self.progress_animation.state() == QPropertyAnimation.State.Running:
            self.progress_animation.stop()
        # Call the Property's setter directly (assigning to the Property
        # descriptor confuses static type checkers).
        self._set_progress(0.0)

    def _get_offset(self):
        return self._offset

    def _set_offset(self, value):
        self._offset = value
        self._offset_changed.emit()
        self.update()

    offset = Property(float, _get_offset, _set_offset, notify=_offset_changed)

    def start_animation(self, duration: int | None = None):
        if (
            self.current_animation
            and self.current_animation.state() == QPropertyAnimation.State.Running
        ):
            self.current_animation.stop()

        anim = QPropertyAnimation(self, b"offset")

        if duration:
            anim.setDuration(duration)
            anim.setLoopCount(1)
            anim.setEasingCurve(QEasingCurve.Type.OutQuad)
            anim.finished.connect(self.stop_animation)
        else:
            anim.setDuration(1200)
            anim.setLoopCount(-1)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        anim.setStartValue(-1.0)
        anim.setEndValue(2.0)
        self._is_animating = True
        anim.start()

        self.current_animation = anim

    def stop_animation(self):
        self._is_animating = False
        if self.current_animation:
            self.current_animation.stop()
        self.update()
