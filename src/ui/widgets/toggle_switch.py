# toggle_switch.py - Modern animated toggle switch widget.
from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """A custom, modern, animated toggle switch widget."""

    toggled = Signal(bool)
    focusChanged = Signal(bool)

    _track_color_changed = Signal()
    _knob_position_changed = Signal()

    def __init__(self, parent=None, variant="default"):
        super().__init__(parent)
        self.setObjectName("ToggleSwitch")
        self.setFixedSize(52, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._checked = False

        # "default" keeps the green accent used on the Settings page.
        # "sidebar" is monochrome (greyscale only) so the edition switch stays
        # visually restrained and does not steal focus from other elements.
        self._variant = variant
        if variant == "sidebar":
            # Constant track colour in both states; only the knob slides, which
            # reads calmer than a colour-changing track.
            self._track_color_off = QColor("#4A4A4A")
            self._track_color_on = QColor("#4A4A4A")
        else:
            self._track_color_off = QColor("#8B8B8B")
            self._track_color_on = QColor("#28A745")
        self._knob_color = QColor("#FFFFFF")

        self._current_track_color = self._track_color_off
        self._knob_position = 3.0  # Start position (left)

        self.animation_group = QParallelAnimationGroup()

        self.color_animation = QPropertyAnimation(self, b"track_color")
        self.color_animation.setDuration(200)
        self.animation_group.addAnimation(self.color_animation)

        self.knob_animation = QPropertyAnimation(self, b"knob_position")
        self.knob_animation.setDuration(200)
        self.knob_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation_group.addAnimation(self.knob_animation)

    def isChecked(self):
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked

        if checked:
            self.color_animation.setEndValue(self._track_color_on)
            self.knob_animation.setEndValue(float(self.width() - self.height() + 3))
        else:
            self.color_animation.setEndValue(self._track_color_off)
            self.knob_animation.setEndValue(3.0)

        self.animation_group.start()
        self.toggled.emit(self._checked)

    def focusInEvent(self, event):
        """Called when the widget gains focus."""
        super().focusInEvent(event)
        self.focusChanged.emit(True)
        self.update()

    def focusOutEvent(self, event):
        """Called when the widget loses focus."""
        super().focusOutEvent(event)
        self.focusChanged.emit(False)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        track_rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(self._current_track_color)
        if self.hasFocus():
            painter.setPen(QPen(QColor("#28A745"), 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, 13, 13)

        knob_y = (self.height() - 22) / 2
        knob_rect = QRectF(self._knob_position, knob_y, 22, 22)
        painter.setBrush(self._knob_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(knob_rect)

    def mousePressEvent(self, event):
        self.setChecked(not self.isChecked())

    def keyPressEvent(self, event):
        """Handles key presses when the widget has focus."""
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Enter, Qt.Key.Key_Return):
            self.setChecked(not self.isChecked())
        else:
            super().keyPressEvent(event)

    def _get_track_color(self):
        return self._current_track_color

    def _set_track_color(self, color):
        self._current_track_color = color
        self._track_color_changed.emit()
        self.update()

    def _get_knob_position(self):
        return self._knob_position

    def _set_knob_position(self, pos):
        self._knob_position = float(pos)
        self._knob_position_changed.emit()
        self.update()

    track_color = Property(
        QColor,
        _get_track_color,
        _set_track_color,
        notify=_track_color_changed,
    )
    knob_position = Property(
        float,
        _get_knob_position,
        _set_knob_position,
        notify=_knob_position_changed,
    )
