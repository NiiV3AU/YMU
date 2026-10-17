# toggle_switch.py - Modern animated toggle switch widget.
from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRectF,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class ToggleSwitch(QWidget):
    """A custom, modern, animated toggle switch widget."""

    toggled = Signal(bool)
    focusChanged = Signal(bool)

    _track_color_changed = Signal()
    _knob_position_changed = Signal()

    def __init__(self, parent=None, variant="default", theme_manager=None):
        super().__init__(parent)
        self.setObjectName("ToggleSwitch")
        self.setFixedSize(52, 28)
        self._interactive = True
        self.theme_manager = theme_manager
        if self.theme_manager is not None:
            self.theme_manager.themeChanged.connect(self._on_theme_changed)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self.isEnabled()
            else Qt.CursorShape.ForbiddenCursor
        )
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._checked = False

        # "default" keeps the green accent used on the Settings page.
        # "sidebar" is monochrome (greyscale only) so the edition switch stays
        # visually restrained and does not steal focus from other elements.
        self._variant = variant
        is_light = self._is_light_theme()
        if variant == "sidebar":
            # Constant track colour in both states; only the knob slides, which
            # reads calmer than a colour-changing track.
            self._track_color_off = QColor("#4A4A4A")
            self._track_color_on = QColor("#4A4A4A")
        else:
            self._track_color_off = QColor("#8B8B8B")
            self._track_color_on = QColor("#218838" if is_light else "#28A745")
        self._knob_color = QColor("#FFFFFF")

        self._current_track_color = self._track_color_off
        self._knob_position = self._target_knob_position(self._checked)

        self.animation_group = QParallelAnimationGroup(self)

        self.color_animation = QPropertyAnimation(self, b"track_color", self)
        self.color_animation.setDuration(200)
        self.animation_group.addAnimation(self.color_animation)

        self.knob_animation = QPropertyAnimation(self, b"knob_position", self)
        self.knob_animation.setDuration(200)
        self.knob_animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation_group.addAnimation(self.knob_animation)

    def _target_knob_position(self, checked: bool) -> float:
        """Returns the knob position based on checked state and layout direction."""
        left_pos = 3.0
        right_pos = float(self.width() - self.height() + 3)
        if self.isRightToLeft():
            return left_pos if checked else right_pos
        return right_pos if checked else left_pos

    def isChecked(self):
        return self._checked

    def setChecked(self, checked: bool):
        if self._checked == checked:
            return
        self._checked = checked

        if self.animation_group.state() == QParallelAnimationGroup.State.Running:
            self.animation_group.stop()
        self.color_animation.setStartValue(self._current_track_color)
        if checked:
            self.color_animation.setEndValue(self._track_color_on)
        else:
            self.color_animation.setEndValue(self._track_color_off)
        self.knob_animation.setStartValue(self._knob_position)
        self.knob_animation.setEndValue(self._target_knob_position(checked))

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

    def isInteractive(self) -> bool:
        return self._interactive

    def setInteractive(self, interactive: bool):
        """When not interactive, the toggle is dimmed and shows a forbidden cursor without disabling mouse hit-testing."""
        if self._interactive == interactive:
            return
        self._interactive = interactive
        if interactive:
            self.setCursor(
                Qt.CursorShape.PointingHandCursor
                if self.isEnabled()
                else Qt.CursorShape.ForbiddenCursor
            )
            self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        else:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.update()

    def changeEvent(self, event):
        """Reacts to state changes, such as enabling/disabling or layout direction changes."""
        if event.type() == QEvent.Type.EnabledChange:
            if not self._interactive:
                self.setCursor(Qt.CursorShape.ForbiddenCursor)
            else:
                self.setCursor(
                    Qt.CursorShape.PointingHandCursor
                    if self.isEnabled()
                    else Qt.CursorShape.ForbiddenCursor
                )
            self.update()
        elif event.type() == QEvent.Type.LayoutDirectionChange:
            target = self._target_knob_position(self._checked)
            if self.animation_group.state() == QParallelAnimationGroup.State.Running:
                self.knob_animation.setEndValue(target)
            else:
                self._set_knob_position(target)
        super().changeEvent(event)

    def _is_light_theme(self) -> bool:
        if self.theme_manager is not None:
            return getattr(self.theme_manager, "current_theme", "dark") == "light"
        win = self.window()
        tm = getattr(win, "theme_manager", None)
        if tm is not None:
            return getattr(tm, "current_theme", "dark") == "light"
        return False

    @Slot(str)
    def _on_theme_changed(self, theme: str):
        if self._variant != "sidebar":
            self._track_color_on = QColor("#218838" if theme == "light" else "#28A745")
            if self._checked:
                self._current_track_color = self._track_color_on
            self.color_animation.setEndValue(
                self._track_color_on if self._checked else self._track_color_off
            )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.isEnabled() or not self._interactive:
            painter.setOpacity(0.38)

        track_rect = self.rect().adjusted(2, 2, -2, -2)
        painter.setBrush(self._current_track_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(track_rect, 12, 12)

        if self.hasFocus():
            is_light = self._is_light_theme()
            ring_color = QColor("#1E7E34" if is_light else "#38D65B")
            painter.setPen(QPen(ring_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            focus_rect = self.rect().adjusted(1, 1, -1, -1)
            painter.drawRoundedRect(focus_rect, 13, 13)

        knob_y = (self.height() - 22) / 2
        knob_rect = QRectF(self._knob_position, knob_y, 22, 22)
        painter.setBrush(self._knob_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(knob_rect)

    def mousePressEvent(self, event):
        if not self.isEnabled() or not self._interactive:
            return
        event.accept()
        self.setChecked(not self.isChecked())

    def keyPressEvent(self, event):
        """Handles key presses when the widget has focus."""
        if not self.isEnabled() or not self._interactive:
            return
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Enter, Qt.Key.Key_Return):
            event.accept()
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
