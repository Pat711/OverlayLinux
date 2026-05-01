from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QColor, QPen, QPainterPath

from drawing_state import DrawingState
from window_manager import get_window_geometry


class OverlayWindow(QWidget):
    # Both signals are safe to emit from non-Qt threads (queued connection)
    strokes_updated = pyqtSignal()
    window_selected = pyqtSignal(str)  # win_id → reposition overlay on Qt thread

    def __init__(self, drawing_state: DrawingState):
        super().__init__()
        self._state = drawing_state
        self._last_geom = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.X11BypassWindowManagerHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.strokes_updated.connect(self.update)
        self.window_selected.connect(self.show_for_window)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._track_target_window)
        self._timer.start(500)

    def show_for_window(self, win_id: str) -> None:
        try:
            x, y, w, h = get_window_geometry(win_id)
        except ValueError:
            return
        self._last_geom = (x, y, w, h)
        self.setGeometry(x, y, w, h)
        self.show()
        self._apply_click_through()

    def _apply_click_through(self) -> None:
        try:
            import Xlib.display
            import Xlib.ext.shape as shape

            display = Xlib.display.Display()
            xid = int(self.winId())
            win = display.create_resource_object("window", xid)
            # Empty rectangle list = no input region = click-through
            win.shape_rectangles(
                shape.SO.Set,   # operation: Set
                shape.SK.Input, # kind: Input (mouse events)
                0,              # ordering: Unsorted
                0, 0,           # x/y offset
                []              # no rectangles → empty input region
            )
            display.sync()
        except Exception:
            # Fallback: Qt-level transparency for mouse events (less reliable)
            self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def _track_target_window(self) -> None:
        win_id = self._state.get_selected_window()
        if not win_id:
            return
        try:
            geom = get_window_geometry(win_id)
        except ValueError:
            self.hide()
            return
        if geom != self._last_geom:
            self._last_geom = geom
            self.setGeometry(*geom)
            self._apply_click_through()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Clear to fully transparent
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.fillRect(self.rect(), Qt.transparent)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)

        w, h = self.width(), self.height()
        if w == 0 or h == 0:
            return

        for stroke in self._state.get_strokes():
            if len(stroke.points) < 2:
                continue
            color = QColor(stroke.color)
            color.setAlphaF(stroke.opacity)
            pen = QPen(color, stroke.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)

            path = QPainterPath()
            px, py = stroke.points[0]
            path.moveTo(px * w, py * h)
            for px, py in stroke.points[1:]:
                path.lineTo(px * w, py * h)
            painter.drawPath(path)
