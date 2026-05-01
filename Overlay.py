import os
import sys
import socket
import threading

os.environ.setdefault("DISPLAY", ":0")

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

from drawing_state import DrawingState
from overlay_window import OverlayWindow
from web_server import run_server


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main():
    QApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
    app = QApplication(sys.argv)

    state = DrawingState()
    overlay = OverlayWindow(state)

    # Called from Flask thread → only emit Qt signals (queued, thread-safe).
    def on_state_change():
        win_id = state.get_selected_window()
        if win_id:
            overlay.window_selected.emit(win_id)
        overlay.strokes_updated.emit()

    state.set_change_callback(on_state_change)

    port = 5000
    ip = get_local_ip()

    server_thread = threading.Thread(
        target=run_server,
        args=(state, overlay),
        kwargs={"host": "0.0.0.0", "port": port},
        daemon=True,
    )
    server_thread.start()

    print(f"Overlay gestartet.")
    print(f"Web-Interface: http://localhost:{port}")
    print(f"Im Netzwerk:   http://{ip}:{port}")
    print("Strg+C zum Beenden.")

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
