import threading
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable


@dataclass
class Stroke:
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#ff0000"
    width: int = 4
    opacity: float = 1.0


class DrawingState:
    def __init__(self):
        self._lock = threading.Lock()
        self._strokes: List[Stroke] = []
        self._current_stroke: Optional[Stroke] = None
        self._selected_window_id: Optional[str] = None
        self._on_change: Optional[Callable] = None

    def set_change_callback(self, cb: Callable) -> None:
        self._on_change = cb

    def _notify(self) -> None:
        if self._on_change:
            self._on_change()

    def begin_stroke(self, color: str, width: int, opacity: float) -> None:
        with self._lock:
            self._current_stroke = Stroke(color=color, width=width, opacity=opacity)

    def add_point_to_current(self, point: Tuple[float, float]) -> None:
        with self._lock:
            if self._current_stroke is not None:
                self._current_stroke.points.append(point)
        self._notify()

    def commit_stroke(self) -> None:
        with self._lock:
            if self._current_stroke is not None and len(self._current_stroke.points) >= 1:
                self._strokes.append(self._current_stroke)
            self._current_stroke = None
        self._notify()

    def clear(self) -> None:
        with self._lock:
            self._strokes.clear()
            self._current_stroke = None
        self._notify()

    def get_strokes(self) -> List[Stroke]:
        with self._lock:
            result = list(self._strokes)
            if self._current_stroke is not None:
                result.append(self._current_stroke)
            return result

    def set_selected_window(self, win_id: str) -> None:
        with self._lock:
            self._selected_window_id = win_id
            self._strokes.clear()
            self._current_stroke = None
        self._notify()

    def get_selected_window(self) -> Optional[str]:
        with self._lock:
            return self._selected_window_id
