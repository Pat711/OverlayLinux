import subprocess
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class WindowInfo:
    win_id: str
    title: str
    x: int
    y: int
    width: int
    height: int
    desktop: int


def list_windows() -> List[WindowInfo]:
    try:
        result = subprocess.run(
            ["wmctrl", "-lG"],
            capture_output=True, text=True, timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    windows = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 8)
        if len(parts) < 9:
            continue
        win_id = parts[0]
        try:
            desktop = int(parts[1])
        except ValueError:
            continue
        # desktop == -1 means "sticky" (visible on all desktops, e.g. Firefox).
        # Exclude only non-normal window types (desktop, dock, etc.).
        if desktop == -1 and not _is_normal_window(win_id):
            continue
        title = parts[8].strip()
        if not title or title == "N/A":
            continue
        # Use xwininfo for accurate absolute coordinates
        geom = _get_geometry_xwininfo(win_id)
        if geom is None:
            continue
        x, y, w, h = geom
        if w <= 0 or h <= 0:
            continue
        windows.append(WindowInfo(
            win_id=win_id, title=title,
            x=x, y=y, width=w, height=h, desktop=desktop
        ))

    windows.sort(key=lambda w: w.title.lower())
    return windows


def _is_normal_window(win_id: str) -> bool:
    try:
        result = subprocess.run(
            ["xprop", "-id", win_id, "_NET_WM_WINDOW_TYPE"],
            capture_output=True, text=True, timeout=3
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True  # assume normal if xprop unavailable
    return "_NET_WM_WINDOW_TYPE_NORMAL" in result.stdout


def _get_geometry_xwininfo(win_id: str) -> Optional[Tuple[int, int, int, int]]:
    try:
        result = subprocess.run(
            ["xwininfo", "-id", win_id],
            capture_output=True, text=True, timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    if result.returncode != 0:
        return None

    x = y = w = h = None
    for line in result.stdout.splitlines():
        line = line.strip()
        m = re.match(r"Absolute upper-left X:\s+(-?\d+)", line)
        if m:
            x = int(m.group(1))
        m = re.match(r"Absolute upper-left Y:\s+(-?\d+)", line)
        if m:
            y = int(m.group(1))
        m = re.match(r"Width:\s+(\d+)", line)
        if m:
            w = int(m.group(1))
        m = re.match(r"Height:\s+(\d+)", line)
        if m:
            h = int(m.group(1))

    if None in (x, y, w, h):
        return None
    return (x, y, w, h)


def get_window_geometry(win_id: str) -> Tuple[int, int, int, int]:
    geom = _get_geometry_xwininfo(win_id)
    if geom is None:
        raise ValueError(f"Cannot get geometry for window {win_id}")
    return geom


def capture_screenshot_png(win_id: str) -> bytes:
    xwd = subprocess.run(
        ["xwd", "-id", win_id, "-silent"],
        capture_output=True, timeout=10
    )
    if xwd.returncode != 0:
        raise RuntimeError(f"xwd failed for window {win_id}")

    convert = subprocess.run(
        ["convert", "xwd:-", "png:-"],
        input=xwd.stdout, capture_output=True, timeout=15
    )
    if convert.returncode != 0:
        raise RuntimeError("convert failed")
    return convert.stdout
