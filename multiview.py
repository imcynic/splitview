#!/usr/bin/env python3
import os
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

import sys
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
from threading import Thread
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QTextEdit, QScrollArea, QComboBox, QGridLayout,
    QSizePolicy, QTabWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QFont

from ssap import SSAPClient

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "multiview.log"),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger("multiview")

LOG_FILE = Path(__file__).parent / "error_docs.json"


class Bridge(QObject):
    connected = Signal(bool)
    inputs_ready = Signal(list)
    services_ready = Signal(list)
    probe_done = Signal(dict)
    log_msg = Signal(str)
    info_ready = Signal(dict)
    raw_response = Signal(str)


class AsyncRunner:
    def __init__(self):
        self.loop: asyncio.AbstractEventLoop = None
        self.thread: Thread = None

    def start(self):
        self.loop = asyncio.new_event_loop()
        self.thread = Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)


class StatusDot(QLabel):
    def __init__(self):
        super().__init__()
        self.setFixedSize(10, 10)
        self.set_color("#f87171")

    def set_color(self, color):
        self.setStyleSheet(
            f"background-color: {color}; border-radius: 5px;"
        )


class InputCard(QFrame):
    def __init__(self, input_data: dict, on_select):
        super().__init__()
        self.input_data = input_data
        self.selected = False
        self.on_select = on_select
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self._setup()

    def _setup(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self.dot = StatusDot()
        connected = self.input_data.get("connected", False)
        self.dot.set_color("#4ade80" if connected else "#555")
        layout.addWidget(self.dot)

        info = QVBoxLayout()
        info.setSpacing(0)
        label = self.input_data.get("label", self.input_data.get("id", "?"))
        name = QLabel(label)
        name.setFont(QFont("Inter", 9, QFont.Bold))
        info.addWidget(name)

        port = self.input_data.get("id", "")
        sub = QLabel(port)
        sub.setFont(QFont("Inter", 8))
        sub.setStyleSheet("color: #888;")
        info.addWidget(sub)
        layout.addLayout(info)
        layout.addStretch()

        self._update_style()

    def _update_style(self):
        border = "#7c3aed" if self.selected else "#2d2d4a"
        bg = "#2a2040" if self.selected else "#1e1e36"
        self.setStyleSheet(
            f"InputCard {{ background: {bg}; border: 1px solid {border}; border-radius: 8px; }}"
        )

    def mousePressEvent(self, event):
        self.selected = not self.selected
        self._update_style()
        self.on_select(self.input_data["id"], self.selected)


class MultiViewApp(QWidget):
    def __init__(self):
        super().__init__()
        self.client: SSAPClient = None
        self.bridge = Bridge()
        self.runner = AsyncRunner()
        self.runner.start()
        self.selected_inputs: list[str] = []
        self.input_cards: list[InputCard] = []

        self.setWindowTitle("MultiView")
        self.resize(240, 600)

        self._setup_ui()
        self._connect_signals()

    def _connect_signals(self):
        self.bridge.connected.connect(self._on_connected)
        self.bridge.inputs_ready.connect(self._on_inputs)
        self.bridge.services_ready.connect(self._on_services)
        self.bridge.probe_done.connect(self._on_probe_done)
        self.bridge.log_msg.connect(self._append_log)
        self.bridge.info_ready.connect(self._on_info)
        self.bridge.raw_response.connect(self._on_raw_response)

    def _setup_ui(self):
        self.setStyleSheet("""
            QWidget { background-color: #12121f; color: #e0e0e0; }
            QPushButton {
                background-color: #2d2d4a; border: 1px solid #3d3d5c;
                border-radius: 6px; padding: 6px; color: #e0e0e0;
                font-size: 11px; font-weight: 500;
            }
            QPushButton:hover { background-color: #3d3d5c; }
            QPushButton:pressed { background-color: #4d4d6c; }
            QPushButton:disabled { background-color: #1a1a2e; color: #444; border-color: #222; }
            QLineEdit {
                background-color: #1e1e36; border: 1px solid #3d3d5c;
                border-radius: 6px; padding: 5px; color: #e0e0e0; font-size: 11px;
            }
            QTextEdit {
                background-color: #0d0d18; border: 1px solid #2d2d4a;
                border-radius: 6px; padding: 4px; color: #aaa;
                font-family: monospace; font-size: 9px;
            }
            QComboBox {
                background-color: #1e1e36; border: 1px solid #3d3d5c;
                border-radius: 6px; padding: 6px; color: #e0e0e0;
            }
            QTabWidget::pane { border: none; background: #12121f; }
            QTabBar::tab {
                background: #1a1a2e; color: #888; padding: 5px 8px;
                border: none; border-bottom: 2px solid transparent; font-size: 10px;
            }
            QTabBar::tab:selected { color: #e0e0e0; border-bottom: 2px solid #7c3aed; }
            QScrollArea { border: none; background: transparent; }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        title = QLabel("MultiView")
        title.setFont(QFont("Inter", 12, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #fff;")
        layout.addWidget(title)

        sub = QLabel("LG TV Controller")
        sub.setFont(QFont("Inter", 8))
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("color: #666;")
        layout.addWidget(sub)

        # Connection
        self._add_separator(layout)
        self._add_header(layout, "CONNECTION")

        conn_row = QHBoxLayout()
        self.ip_input = QLineEdit("192.168.1.191")
        self.ip_input.setPlaceholderText("TV IP address")
        conn_row.addWidget(self.ip_input)

        self.conn_dot = StatusDot()
        conn_row.addWidget(self.conn_dot)
        layout.addLayout(conn_row)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._do_connect)
        layout.addWidget(self.connect_btn)

        self.status_label = QLabel("Disconnected")
        self.status_label.setFont(QFont("Inter", 9))
        self.status_label.setStyleSheet("color: #f87171;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Tabs
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        # -- Inputs tab --
        inputs_tab = QWidget()
        inputs_layout = QVBoxLayout(inputs_tab)
        inputs_layout.setContentsMargins(0, 8, 0, 0)
        inputs_layout.setSpacing(8)

        self._add_header(inputs_layout, "HDMI INPUTS")

        self.inputs_scroll = QScrollArea()
        self.inputs_scroll.setWidgetResizable(True)
        self.inputs_container = QWidget()
        self.inputs_list = QVBoxLayout(self.inputs_container)
        self.inputs_list.setSpacing(6)
        self.inputs_list.setContentsMargins(0, 0, 0, 0)
        self.inputs_list.addStretch()
        self.inputs_scroll.setWidget(self.inputs_container)
        inputs_layout.addWidget(self.inputs_scroll, 1)

        self.refresh_btn = QPushButton("Refresh Inputs")
        self.refresh_btn.clicked.connect(self._do_refresh_inputs)
        self.refresh_btn.setEnabled(False)
        inputs_layout.addWidget(self.refresh_btn)

        self._add_header(inputs_layout, "LAYOUT")

        self.layout_combo = QComboBox()
        self.layout_combo.addItems([
            "side-by-side", "top-bottom", "pip-top-right",
            "pip-top-left", "pip-bottom-right", "pip-bottom-left",
            "grid-2x2",
        ])
        inputs_layout.addWidget(self.layout_combo)

        self.apply_btn = QPushButton("Apply MultiView")
        self.apply_btn.setStyleSheet(
            "QPushButton { background: #7c3aed; border-color: #9333ea; }"
            "QPushButton:hover { background: #9333ea; }"
            "QPushButton:disabled { background: #2a2040; border-color: #333; color: #555; }"
        )
        self.apply_btn.clicked.connect(self._do_apply_multiview)
        self.apply_btn.setEnabled(False)
        inputs_layout.addWidget(self.apply_btn)

        self.disable_btn = QPushButton("Disable MultiView")
        self.disable_btn.clicked.connect(self._do_disable_multiview)
        self.disable_btn.setEnabled(False)
        inputs_layout.addWidget(self.disable_btn)

        tabs.addTab(inputs_tab, "Inputs")

        # -- Probe tab --
        probe_tab = QWidget()
        probe_layout = QVBoxLayout(probe_tab)
        probe_layout.setContentsMargins(0, 8, 0, 0)
        probe_layout.setSpacing(8)

        self.probe_btn = QPushButton("Probe MultiView APIs")
        self.probe_btn.clicked.connect(self._do_probe)
        self.probe_btn.setEnabled(False)
        probe_layout.addWidget(self.probe_btn)

        self.services_btn = QPushButton("List Services")
        self.services_btn.clicked.connect(self._do_list_services)
        self.services_btn.setEnabled(False)
        probe_layout.addWidget(self.services_btn)

        self.info_btn = QPushButton("TV Info")
        self.info_btn.clicked.connect(self._do_get_info)
        self.info_btn.setEnabled(False)
        probe_layout.addWidget(self.info_btn)

        self._add_header(probe_layout, "RAW COMMAND")
        self.raw_uri = QLineEdit()
        self.raw_uri.setPlaceholderText("ssap://...")
        probe_layout.addWidget(self.raw_uri)

        self.raw_payload = QLineEdit()
        self.raw_payload.setPlaceholderText('{"key": "value"} (optional)')
        probe_layout.addWidget(self.raw_payload)

        self.raw_btn = QPushButton("Send")
        self.raw_btn.clicked.connect(self._do_raw_send)
        self.raw_btn.setEnabled(False)
        probe_layout.addWidget(self.raw_btn)

        probe_layout.addStretch()
        tabs.addTab(probe_tab, "Probe")

        # -- Log tab --
        log_tab = QWidget()
        log_layout = QVBoxLayout(log_tab)
        log_layout.setContentsMargins(0, 8, 0, 0)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text, 1)

        export_row = QHBoxLayout()
        export_btn = QPushButton("Export Errors")
        export_btn.clicked.connect(self._do_export_errors)
        export_row.addWidget(export_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.log_text.clear())
        export_row.addWidget(clear_btn)
        log_layout.addLayout(export_row)

        tabs.addTab(log_tab, "Log")

    def _add_separator(self, layout):
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #2d2d4a;")
        layout.addWidget(sep)

    def _add_header(self, layout, text):
        h = QLabel(text)
        h.setFont(QFont("Inter", 7, QFont.Bold))
        h.setStyleSheet("color: #555; letter-spacing: 1px;")
        layout.addWidget(h)

    def _set_controls_enabled(self, enabled):
        for btn in (self.refresh_btn, self.probe_btn, self.services_btn,
                    self.info_btn, self.raw_btn, self.apply_btn, self.disable_btn):
            btn.setEnabled(enabled)

    def _do_connect(self):
        ip = self.ip_input.text().strip()
        if not ip:
            return
        self.connect_btn.setEnabled(False)
        self.status_label.setText("Connecting...")
        self.status_label.setStyleSheet("color: #fbbf24;")
        self._append_log(f"Connecting to {ip}...")

        self.client = SSAPClient(ip)
        self.client.on_status_change = lambda ok: self.bridge.connected.emit(ok)

        async def do():
            try:
                await self.client.connect()
            except Exception as e:
                self.bridge.log_msg.emit(f"Connection error: {e}")
                self.bridge.connected.emit(False)

        self.runner.run(do())

    def _on_connected(self, ok):
        self.connect_btn.setEnabled(True)
        if ok:
            self.conn_dot.set_color("#4ade80")
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #4ade80;")
            self.connect_btn.setText("Disconnect")
            self.connect_btn.clicked.disconnect()
            self.connect_btn.clicked.connect(self._do_disconnect)
            self._set_controls_enabled(True)
            self._append_log("Connected and registered")
            self._do_refresh_inputs()
        else:
            self.conn_dot.set_color("#f87171")
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #f87171;")
            self.connect_btn.setText("Connect")
            try:
                self.connect_btn.clicked.disconnect()
            except RuntimeError:
                pass
            self.connect_btn.clicked.connect(self._do_connect)
            self._set_controls_enabled(False)

    def _do_disconnect(self):
        if self.client:
            self.runner.run(self.client.disconnect())

    def _do_refresh_inputs(self):
        async def do():
            inputs = await self.client.get_inputs()
            self.bridge.inputs_ready.emit(inputs)

        self.runner.run(do())

    def _on_inputs(self, inputs):
        while self.inputs_list.count() > 1:
            item = self.inputs_list.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self.input_cards.clear()
        self.selected_inputs.clear()
        self._append_log(f"Found {len(inputs)} inputs")

        for inp in inputs:
            card = InputCard(inp, self._on_input_select)
            self.inputs_list.insertWidget(self.inputs_list.count() - 1, card)
            self.input_cards.append(card)

    def _on_input_select(self, input_id, selected):
        if selected and input_id not in self.selected_inputs:
            self.selected_inputs.append(input_id)
        elif not selected and input_id in self.selected_inputs:
            self.selected_inputs.remove(input_id)
        self._append_log(f"Selected: {self.selected_inputs}")

    def _do_apply_multiview(self):
        layout = self.layout_combo.currentText()
        inputs = list(self.selected_inputs)
        self._append_log(f"Applying: layout={layout} inputs={inputs}")

        async def do():
            results = await self.client.try_multiview(
                "set_layout", inputs=inputs, layout=layout
            )
            self.bridge.probe_done.emit(results)

        self.runner.run(do())

    def _do_disable_multiview(self):
        self._append_log("Disabling MultiView...")

        async def do():
            results = await self.client.try_multiview("disable")
            self.bridge.probe_done.emit(results)

        self.runner.run(do())

    def _do_probe(self):
        self._append_log("Probing MultiView APIs...")
        self.probe_btn.setEnabled(False)

        async def do():
            results = await self.client.probe_multiview()
            self.bridge.probe_done.emit(results)
            self.bridge.log_msg.emit("Probe complete")

        self.runner.run(do())

    def _on_probe_done(self, results):
        self.probe_btn.setEnabled(True)
        for uri, r in results.items():
            status = "OK" if r["success"] else r["error"] or r["type"]
            self._append_log(f"  {uri}\n    -> {status}")
            if r["success"]:
                self._append_log(f"    payload: {json.dumps(r['payload'], indent=2)}")

    def _do_list_services(self):
        async def do():
            services = await self.client.get_services()
            self.bridge.services_ready.emit(services)

        self.runner.run(do())

    def _on_services(self, services):
        self._append_log(f"=== {len(services)} services ===")
        for s in sorted(services, key=lambda x: x.get("name", "")):
            name = s.get("name", "?")
            self._append_log(f"  {name}")

    def _do_get_info(self):
        async def do():
            sys_info = await self.client.get_system_info()
            dev_info = await self.client.get_device_info()
            sw_info = await self.client.send(
                "ssap://com.webos.service.update/getCurrentSWInformation"
            )
            combined = {
                "system": sys_info,
                "device": dev_info,
                "software": sw_info.get("payload", {}),
            }
            self.bridge.info_ready.emit(combined)

        self.runner.run(do())

    def _on_info(self, info):
        self._append_log("=== TV Info ===")
        self._append_log(json.dumps(info, indent=2))

    def _do_raw_send(self):
        uri = self.raw_uri.text().strip()
        if not uri:
            return
        payload_text = self.raw_payload.text().strip()
        payload = None
        if payload_text:
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                self._append_log(f"Invalid JSON: {payload_text}")
                return

        self._append_log(f">>> {uri} {payload or ''}")

        async def do():
            resp = await self.client.send_raw(uri, payload)
            self.bridge.raw_response.emit(json.dumps(resp, indent=2))

        self.runner.run(do())

    def _on_raw_response(self, text):
        self._append_log(f"<<< {text}")

    def _append_log(self, text):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{ts}] {text}")

    def _do_export_errors(self):
        if not self.client:
            return
        log_data = self.client.export_error_log()
        LOG_FILE.write_text(log_data)
        self._append_log(f"Errors exported to {LOG_FILE}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MultiViewApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
