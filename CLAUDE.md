# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the application

```bash
# Recommended: use the bundled launcher (resolves venv automatically)
./start.sh

# Or activate the venv manually
source .venv/bin/activate
python Overlay.py
```

The app prints the local network URL on startup (`http://<LAN-IP>:5000`). A graphical display (`$DISPLAY`) must be available — it creates a Qt window.

## Setting up the venv

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# System tools also required: wmctrl, xwininfo, xwd, convert (ImageMagick)
```

## Architecture

The program has two concurrent halves that must never call each other's APIs directly:

**Main thread — PyQt5**
- `Overlay.py` — entry point; boots `QApplication`, wires everything together
- `overlay_window.py` — `OverlayWindow(QWidget)`: frameless, always-on-top, fully transparent window that renders the drawing on top of the selected X11 window

**Daemon thread — Flask**
- `web_server.py` — Flask + Flask-SocketIO (`async_mode="threading"`); serves the web UI and handles all Socket.IO events
- `templates/index.html` — single-page app; window list on the left, drawing canvas on the right

**Shared neutral layer**
- `drawing_state.py` — `DrawingState`: the only object both threads touch. All mutations are protected by `threading.Lock`. Read with `get_strokes()` (returns a snapshot copy).
- `window_manager.py` — pure subprocess calls (`wmctrl`, `xwininfo`, `xwd | convert`); no Qt or Flask dependency

## Thread-crossing rule

The Flask thread must **never** call Qt methods directly. The only safe crossing point is emitting `pyqtSignal`s, which Qt auto-delivers on the main thread via the event queue:

```
Flask thread                    Qt main thread
─────────────────────────────   ──────────────────────────────
DrawingState mutation           ← (lock-protected)
on_state_change() callback
  overlay.strokes_updated.emit()  →  OverlayWindow.update() → paintEvent()
  overlay.window_selected.emit()  →  OverlayWindow.show_for_window()
```

`OverlayWindow` exposes two signals for this purpose: `strokes_updated = pyqtSignal()` and `window_selected = pyqtSignal(str)`.

## Coordinate system

All stroke coordinates are stored and transmitted as **normalized floats (0.0–1.0)** relative to the canvas/window dimensions. The browser sends `clientX / rect.width`; `paintEvent` converts back with `px * self.width()`. This keeps browser resolution and overlay resolution independent.

## Click-through on X11

`OverlayWindow._apply_click_through()` uses the X11 SHAPE extension to set an empty input region on the window (`win.shape_rectangles(..., SK.Input, ..., [])`). This must be called **after** `self.show()` (before that, `winId()` is not yet valid). Falls back to `WA_TransparentForMouseEvents` if Xlib is unavailable.

## Window tracking

A 500 ms `QTimer` in `OverlayWindow` polls the selected window's geometry via `xwininfo` and calls `setGeometry()` if it changed. If `xwininfo` returns a non-zero exit code (window was closed), the overlay hides itself.

## Socket.IO events

| Event (client→server) | Payload | Effect |
|---|---|---|
| `select_window` | `{win_id}` | Clears strokes, repositions overlay |
| `stroke_begin` | `{color, width, opacity}` | Starts a new stroke |
| `stroke_point` | `{x, y}` | Appends point; broadcast to other clients |
| `stroke_end` | `{}` | Commits stroke |
| `clear` | `{}` | Clears all strokes; broadcast |
| `sync_request` | `{}` | Server replies with full stroke list |
