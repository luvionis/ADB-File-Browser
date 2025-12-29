from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QLineEdit, QHBoxLayout, 
    QCheckBox, QPushButton, QMessageBox, QPlainTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QTcpSocket, QHostAddress
from PyQt6.QtGui import QPixmap
import subprocess

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setFixedSize(300, 100)
        layout = QVBoxLayout()
        self.label = QLabel("Please wait, processing files...")
        layout.addWidget(self.label)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

class WiFiConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("WiFi ADB Connection")
        self.parent_ref = parent # Needs reference to call update_devices or similar methods if needed, or use signals.
        # Ideally, this should emit signals, but for quick refactor we might keep it tight.
        # But separate file means we can't easily access parent methods unless we pass them or use signals.
        # I will change it to self-contained logic where possible or emit signals.
        
        layout = QVBoxLayout()

        # IP and Port Input
        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("IP Address:"))
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("192.168.1.100")
        ip_layout.addWidget(self.ip_edit)
        layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Port:"))
        self.port_edit = QLineEdit("5555")
        port_layout.addWidget(self.port_edit)
        layout.addLayout(port_layout)

        # Pairing Code Section
        self.pair_check = QCheckBox("Use Pairing Code")
        self.pair_check.stateChanged.connect(self.toggle_pairing_fields)
        layout.addWidget(self.pair_check)

        self.pair_code_layout = QHBoxLayout()
        self.pair_code_layout.addWidget(QLabel("Pairing Code:"))
        self.pair_code_edit = QLineEdit()
        self.pair_code_edit.setEnabled(False)
        self.pair_code_layout.addWidget(self.pair_code_edit)
        layout.addLayout(self.pair_code_layout)

        # Port Scanning
        self.scan_ports_check = QCheckBox("Scan Common Ports (5555-5585)")
        layout.addWidget(self.scan_ports_check)

        # Connection Buttons
        btn_layout = QHBoxLayout()
        connect_btn = QPushButton("Connect")
        connect_btn.clicked.connect(self.handle_wifi_connection)
        btn_layout.addWidget(connect_btn)

        usb_btn = QPushButton("Reset via USB")
        usb_btn.clicked.connect(self.reset_adb_over_usb)
        btn_layout.addWidget(usb_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

        self.progress_bar = QProgressBar() # Internal one if needed or use simple cursor wait
        layout.addWidget(self.progress_bar)
        self.progress_bar.setVisible(False)

    def toggle_pairing_fields(self, state):
        self.pair_code_edit.setEnabled(self.pair_check.isChecked())

    def handle_wifi_connection(self):
        ip = self.ip_edit.text().strip()
        port = self.port_edit.text().strip()
        use_pairing = self.pair_check.isChecked()
        pairing_code = self.pair_code_edit.text() if use_pairing else None

        if not ip:
            QMessageBox.warning(self, "Error", "Please enter IP address!")
            return

        if self.scan_ports_check.isChecked():
            self.scan_ports(ip)
        else:
            if use_pairing:
                self.pair_device(ip, port, pairing_code)
            self.connect_to_device(ip, port)
            self.close()

    def pair_device(self, ip, port, code):
        try:
            cmd = ["adb", "pair", f"{ip}:{port}", code]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if "Successfully paired" in result.stdout:
                QMessageBox.information(self, "Success", "Pairing successful!")
            else:
                QMessageBox.critical(self, "Error", f"Pairing failed: {result.stderr}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Pairing error: {str(e)}")

    def connect_to_device(self, ip, port="5555"):
        self.progress_bar.setVisible(True)
        try:
            cmd = ["adb", "connect", f"{ip}:{port}"]
            result = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.STDOUT)
            if "connected" in result:
                QMessageBox.information(self, "Success", f"Connected to {ip}:{port}")
            else:
                QMessageBox.critical(self, "Error", f"Connection failed: {result}")
        except subprocess.CalledProcessError as e:
            QMessageBox.critical(self, "Error", f"Connection error: {e.output}")
        finally:
            self.progress_bar.setVisible(False)

    def scan_ports(self, ip):
        self.progress_bar.setVisible(True)
        found = False
        # Limit scan for UI responsiveness or run in thread... keeping simple for now
        # Ideally should be a thread
        for port in range(5555, 5586):
            try:
                sock = QTcpSocket()
                sock.connectToHost(QHostAddress(ip), port)
                if sock.waitForConnected(100):
                    self.connect_to_device(ip, str(port))
                    found = True
                    break
            except Exception:
                continue
        if not found:
            QMessageBox.warning(self, "Scan Result", "No open ADB ports found!")
        self.progress_bar.setVisible(False)

    def reset_adb_over_usb(self):
        try:
            # Find the USB-connected device
            devices = subprocess.check_output(["adb", "devices"], universal_newlines=True)
            # Simple check for any device
            usb_device = [line.split()[0] for line in devices.splitlines() if "device" in line and not line.startswith("List")]

            if usb_device:
                subprocess.run(["adb", "-s", usb_device[0], "tcpip", "5555"], check=True)
                QMessageBox.information(self, "Success", "Device reset to TCP mode on port 5555")
            else:
                QMessageBox.warning(self, "Error", "No USB device found!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Reset failed: {str(e)}")

class GenericTextDialog(QDialog):
    def __init__(self, title, content, parent=None, width=500, height=300):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout()
        text_edit = QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(content)
        layout.addWidget(text_edit)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        self.setLayout(layout)
        self.resize(width, height)

class ImagePreviewDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Preview")
        layout = QVBoxLayout()
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        self.setLayout(layout)

class SettingsDialog(QDialog):
    def __init__(self, current_refresh, current_interval, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.result_settings = None # (bool, int)
        
        layout = QVBoxLayout()
        self.auto_refresh_cb = QCheckBox("Auto-refresh device list")
        self.auto_refresh_cb.setChecked(current_refresh)
        layout.addWidget(self.auto_refresh_cb)
        
        layout.addWidget(QLabel("Device refresh interval (ms):"))
        self.interval_edit = QLineEdit(str(current_interval))
        layout.addWidget(self.interval_edit)
        
        btn_box = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        btn_box.addWidget(ok_btn)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)
        
        ok_btn.clicked.connect(self.apply_settings)
        cancel_btn.clicked.connect(self.reject)
        self.setLayout(layout)

    def apply_settings(self):
        try:
            interval = int(self.interval_edit.text())
            self.result_settings = (self.auto_refresh_cb.isChecked(), interval)
            self.accept()
        except ValueError:
            QMessageBox.warning(self, "Error", "Invalid interval value")

class TerminalDialog(QDialog):
    def __init__(self, adb_manager_cls, device=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Terminal")
        self.adb_manager = adb_manager_cls
        self.device = device
        
        layout = QVBoxLayout()
        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        layout.addWidget(self.output_edit)
        
        self.input_line = QLineEdit()
        self.input_line.returnPressed.connect(self.send_command)
        layout.addWidget(self.input_line)
        
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_command)
        layout.addWidget(send_btn)
        
        self.setLayout(layout)
        self.resize(600, 400)

    def send_command(self):
        cmd_text = self.input_line.text().strip()
        if not cmd_text:
            return
        cmd = ["adb", "shell"] + cmd_text.split()
        # Use adb manager to build command if needed or manual
        if self.device:
             # Basic implementation of adb -s injection if not using the manager instance (since it is static class mostly)
            # Actually adb_manager_cls was passed as class. 
            cmd = self.adb_manager.build_command(cmd, self.device)
            
        try:
            output = subprocess.check_output(cmd, universal_newlines=True, stderr=subprocess.PIPE)
            self.output_edit.appendPlainText(f"> {cmd_text}\n{output}")
        except subprocess.CalledProcessError as e:
            self.output_edit.appendPlainText(f"> {cmd_text}\nError: {e}")
        self.input_line.clear()
