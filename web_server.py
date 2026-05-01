import io
import logging
import threading
from typing import Callable, Optional

from flask import Flask, jsonify, render_template, send_file, Response
from flask_socketio import SocketIO, emit

logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)
app.config["SECRET_KEY"] = "overlay-secret"
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

_drawing_state = None
_signal_bridge: Optional[Callable] = None
_overlay_window = None


# ── REST ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/windows")
def get_windows():
    from window_manager import list_windows
    windows = list_windows()
    return jsonify([
        {"id": w.win_id, "title": w.title,
         "x": w.x, "y": w.y, "width": w.width, "height": w.height}
        for w in windows
    ])


@app.route("/screenshot/<path:win_id>")
def get_screenshot(win_id: str):
    from window_manager import capture_screenshot_png
    try:
        png_bytes = capture_screenshot_png(win_id)
    except Exception as e:
        return Response(str(e), status=500)
    return send_file(io.BytesIO(png_bytes), mimetype="image/png")


# ── Socket.IO ───────────────────────────────────────────────────────────────

@socketio.on("select_window")
def on_select_window(data):
    win_id = data.get("win_id", "")
    _drawing_state.set_selected_window(win_id)
    # Move overlay to cover the selected window (must happen on Qt main thread)
    if _overlay_window is not None:
        _overlay_window.strokes_updated.emit()
    # Tell all clients to load the new screenshot
    emit("window_selected", {"win_id": win_id}, broadcast=True)


@socketio.on("stroke_begin")
def on_stroke_begin(data):
    _drawing_state.begin_stroke(
        data.get("color", "#ff0000"),
        int(data.get("width", 4)),
        float(data.get("opacity", 1.0)),
    )


@socketio.on("stroke_point")
def on_stroke_point(data):
    _drawing_state.add_point_to_current((float(data["x"]), float(data["y"])))
    emit("stroke_point", data, broadcast=True, include_self=False)


@socketio.on("stroke_end")
def on_stroke_end(_data):
    _drawing_state.commit_stroke()
    emit("stroke_end", {}, broadcast=True, include_self=False)


@socketio.on("clear")
def on_clear(_data):
    _drawing_state.clear()
    emit("clear", {}, broadcast=True)


@socketio.on("sync_request")
def on_sync_request(_data):
    strokes = _drawing_state.get_strokes()
    emit("sync_response", {
        "strokes": [
            {"points": s.points, "color": s.color,
             "width": s.width, "opacity": s.opacity}
            for s in strokes
        ]
    })


# ── Startup ─────────────────────────────────────────────────────────────────

def run_server(drawing_state, overlay_window, host: str = "0.0.0.0", port: int = 5000):
    global _drawing_state, _overlay_window
    _drawing_state = drawing_state
    _overlay_window = overlay_window
    socketio.run(app, host=host, port=port, use_reloader=False, log_output=False)
