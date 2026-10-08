# animated_stacked_widget.py - Smooth animated transitions for stacked widgets.
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QStackedWidget, QWidget


class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget that animates transitions between pages.

    Supports directional sliding (vertical or horizontal) with cubic easing.
    Handles rapid navigation, window resizing, and preserves geometry and
    layout hierarchy.
    """

    animationStarted = Signal(int, int)  # from_index, to_index
    animationFinished = Signal(int)  # current_index

    def __init__(
        self,
        parent: QWidget | None = None,
        duration: int = 240,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        easing_curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic,
    ):
        super().__init__(parent)
        self._duration = duration
        self._orientation = orientation
        self._easing_curve = easing_curve

        self._anim_group = QParallelAnimationGroup(self)
        self._anim_group.finished.connect(self._on_animation_finished)

        self._is_animating = False
        self._prev_index = -1
        self._next_index = -1
        self._anim_curr: QPropertyAnimation | None = None
        self._anim_next: QPropertyAnimation | None = None

    @property
    def duration(self) -> int:
        return self._duration

    @duration.setter
    def duration(self, value: int):
        self._duration = max(50, value)

    @property
    def orientation(self) -> Qt.Orientation:
        return self._orientation

    @orientation.setter
    def orientation(self, value: Qt.Orientation):
        self._orientation = value

    @property
    def easing_curve(self) -> QEasingCurve.Type:
        return self._easing_curve

    @easing_curve.setter
    def easing_curve(self, value: QEasingCurve.Type):
        self._easing_curve = value

    def is_animating(self) -> bool:
        return self._is_animating

    def setCurrentWidget(self, widget: QWidget):
        """Switches to the given widget, animating if visible."""
        index = self.indexOf(widget)
        if index != -1:
            self.setCurrentIndex(index)

    def setCurrentIndex(self, index: int):
        """Switches to the page at index, animating if the widget is visible."""
        if index < 0 or index >= self.count():
            return

        # Interrupted animation: cancel previous and finalize target
        if self._is_animating:
            self._anim_group.stop()
            self._cleanup_transition()

        if index == self.currentIndex():
            return

        # Instant switch when hidden, during initial load, or when only 1 child exists
        if not self.isVisible() or self.count() <= 1:
            super().setCurrentIndex(index)
            return

        curr_idx = self.currentIndex()
        w_curr = self.currentWidget()
        w_next = self.widget(index)
        if not w_curr or not w_next:
            super().setCurrentIndex(index)
            return

        self._prev_index = curr_idx
        self._next_index = index
        self._is_animating = True

        width = self.width()
        height = self.height()

        w_next.setGeometry(0, 0, width, height)

        if self._orientation == Qt.Orientation.Vertical:
            offset_y = height if index > curr_idx else -height
            start_pos_next = QPoint(0, offset_y)
            end_pos_curr = QPoint(0, -offset_y)
        else:
            is_rtl = self.isRightToLeft()
            offset_x = (
                -width
                if (index > curr_idx and is_rtl) or (index < curr_idx and not is_rtl)
                else width
            )
            start_pos_next = QPoint(offset_x, 0)
            end_pos_curr = QPoint(-offset_x, 0)

        w_next.move(start_pos_next)
        w_next.show()
        w_next.raise_()

        # Safely empty previous animations without PySide clear() binding glitch
        while self._anim_group.animationCount() > 0:
            self._anim_group.takeAnimation(0)

        self._anim_curr = QPropertyAnimation(w_curr, b"pos", self)
        self._anim_curr.setDuration(self._duration)
        self._anim_curr.setEasingCurve(self._easing_curve)
        self._anim_curr.setStartValue(QPoint(0, 0))
        self._anim_curr.setEndValue(end_pos_curr)

        self._anim_next = QPropertyAnimation(w_next, b"pos", self)
        self._anim_next.setDuration(self._duration)
        self._anim_next.setEasingCurve(self._easing_curve)
        self._anim_next.setStartValue(start_pos_next)
        self._anim_next.setEndValue(QPoint(0, 0))

        self._anim_group.addAnimation(self._anim_curr)
        self._anim_group.addAnimation(self._anim_next)

        self.animationStarted.emit(curr_idx, index)
        self._anim_group.start()

    def _on_animation_finished(self):
        self._cleanup_transition()
        self.animationFinished.emit(self.currentIndex())

    def _cleanup_transition(self):
        if self._next_index != -1:
            target_idx = self._next_index
            self._next_index = -1
            super().setCurrentIndex(target_idx)

            if self._prev_index != -1:
                prev_widget = self.widget(self._prev_index)
                if prev_widget and prev_widget != self.currentWidget():
                    prev_widget.hide()
                    prev_widget.move(0, 0)
                self._prev_index = -1

            curr_widget = self.currentWidget()
            if curr_widget:
                curr_widget.setGeometry(self.rect())

        self._is_animating = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._is_animating:
            curr = self.currentWidget()
            if curr:
                curr.setGeometry(self.rect())
