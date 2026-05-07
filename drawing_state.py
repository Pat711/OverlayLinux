import threading
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Callable


@dataclass
class Stroke:
    points: List[Tuple[float, float]] = field(default_factory=list)
    color: str = "#ff0000"
    width: int = 4
    opacity: float = 1.0


@dataclass
class GridConfig:
    enabled: bool = False
    type: str = "rect"       # "rect" | "hex"
    hex_style: str = "flat"  # "flat" | "pointy"
    color: str = "#ffffff"
    opacity: float = 0.5
    cell_size: int = 50      # pixels at overlay/canvas resolution


class DrawingState:
    def __init__(self):
        self._lock = threading.Lock()
        self._strokes: List[Stroke] = []
        self._current_stroke: Optional[Stroke] = None
        self._selected_window_id: Optional[str] = None
        self._grid_config: GridConfig = GridConfig()
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

    def get_grid_config(self) -> GridConfig:
        with self._lock:
            cfg = self._grid_config
            return GridConfig(
                enabled=cfg.enabled, type=cfg.type, hex_style=cfg.hex_style,
                color=cfg.color, opacity=cfg.opacity, cell_size=cfg.cell_size,
            )

    def set_grid_config(self, data: dict) -> None:
        with self._lock:
            cfg = self._grid_config
            cfg.enabled   = bool(data.get("enabled", cfg.enabled))
            cfg.type      = str(data.get("type", cfg.type))
            cfg.hex_style = str(data.get("hexStyle", cfg.hex_style))
            cfg.color     = str(data.get("color", cfg.color))
            cfg.opacity   = float(data.get("opacity", cfg.opacity))
            cfg.cell_size = max(10, int(data.get("cellSize", cfg.cell_size)))
        self._notify()
