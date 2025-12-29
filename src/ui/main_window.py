import os
import sys
import logging
import csv
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox,
    QTreeWidget, QTreeWidgetItem, QFileDialog, QHBoxLayout, QProgressBar, QLineEdit,
    QMenu, QAbstractItemView, QInputDialog, QComboBox, QApplication
)
from PyQt6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PyQt6.QtCore import Qt, QTimer, QUrl

from src.utils.icons import create_icon
from src.utils.adb import AdbManager
from src.workers import FileListWorker, AdbCommandWorker, ZipWorker, MultiDownloadWorker
from src.ui.dialogs import (
    ProgressDialog, WiFiConnectionDialog, GenericTextDialog, 
    ImagePreviewDialog, SettingsDialog, TerminalDialog
)
from src.ui.transfer_window import TransferWindow

class AdbFileBrowser(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ADB File Browser")
        self.setGeometry(100, 100, 1100, 700)
        self.setAcceptDrops(True) # Enable Drag & Drop
        
        self.current_directory = "/sdcard"
        self.history = []
        self.forward_history = []
        self.copied_items = []
        self.favorites = []
        self.search_target = None
        
        self.auto_refresh_devices = True
        self.device_refresh_interval = 10000

        self.transfer_window = TransferWindow()
        
        self.init_ui()
        
        self.list_files()
        
        self.connection_timer = QTimer(self)
        self.connection_timer.setInterval(10000)
        self.connection_timer.timeout.connect(self.check_device)
        self.connection_timer.start()

        self.device_timer = QTimer(self)
        self.device_timer.setInterval(self.device_refresh_interval)
        self.device_timer.timeout.connect(self.update_devices)
        self.device_timer.start()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Top Layout
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Current Path:"))
        
        self.path_edit = QLineEdit(self.current_directory)
        self.path_edit.returnPressed.connect(self.on_path_changed)
        top_layout.addWidget(self.path_edit)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.list_files)
        top_layout.addWidget(refresh_btn)
        
        new_folder_btn = QPushButton("New Folder")
        new_folder_btn.clicked.connect(self.create_new_folder)
        top_layout.addWidget(new_folder_btn)
        
        top_layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.update_devices() # Initial population
        top_layout.addWidget(self.device_combo)
        
        # Favorites
        top_layout.addWidget(QLabel("Favorites:"))
        self.favorites_combo = QComboBox()
        self.favorites_combo.addItem("Favorites")
        self.favorites_combo.currentIndexChanged.connect(self.select_favorite)
        top_layout.addWidget(self.favorites_combo)
        
        add_fav_btn = QPushButton("Add Favorite")
        add_fav_btn.clicked.connect(self.add_favorite)
        top_layout.addWidget(add_fav_btn)
        
        remove_fav_btn = QPushButton("Remove Favorite")
        remove_fav_btn.clicked.connect(self.remove_favorite)
        top_layout.addWidget(remove_fav_btn)
        
        # Theme Selection
        top_layout.addWidget(QLabel("Theme:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Default", "Light", "Dark", "Blue", "Green", "Red", "Purple", "Orange", "Black", "Gray", "Teal"])
        self.theme_combo.currentIndexChanged.connect(self.apply_theme)
        top_layout.addWidget(self.theme_combo)

        wifi_connect_btn = QPushButton("WiFi Connect")
        wifi_connect_btn.clicked.connect(self.show_wifi_connection_dialog)
        top_layout.addWidget(wifi_connect_btn)
        
        main_layout.addLayout(top_layout)
        
        # Header & Search
        header_label = QLabel("Browse files on your connected device")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(header_label)
        
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.textChanged.connect(self.filter_files)
        main_layout.addWidget(self.search_bar)
        
        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("File List")
        self.tree.setColumnWidth(0, 500)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        main_layout.addWidget(self.tree)
        
        # Buttons
        button_layout = QHBoxLayout()
        back_btn = QPushButton("◀")
        back_btn.clicked.connect(self.go_back)
        button_layout.addWidget(back_btn)
        
        forward_btn = QPushButton("▶")
        forward_btn.clicked.connect(self.go_forward)
        button_layout.addWidget(forward_btn)
        
        home_btn = QPushButton("🏠")
        home_btn.clicked.connect(self.go_home)
        button_layout.addWidget(home_btn)
        
        download_btn = QPushButton("Download")
        download_btn.clicked.connect(self.download_file)
        button_layout.addWidget(download_btn)
        
        install_btn = QPushButton("Install APK")
        install_btn.clicked.connect(self.install_apk)
        button_layout.addWidget(install_btn)
        
        upload_btn = QPushButton("Upload")
        upload_btn.clicked.connect(self.upload_file)
        button_layout.addWidget(upload_btn)
        
        delete_btn = QPushButton("Delete")
        delete_btn.clicked.connect(self.delete_file)
        button_layout.addWidget(delete_btn)
        
        rename_btn = QPushButton("Rename")
        rename_btn.clicked.connect(self.rename_file)
        button_layout.addWidget(rename_btn)
        
        props_btn = QPushButton("Properties")
        props_btn.clicked.connect(self.show_properties)
        button_layout.addWidget(props_btn)
        
        dev_info_btn = QPushButton("Device Info")
        dev_info_btn.clicked.connect(self.device_info)
        button_layout.addWidget(dev_info_btn)
        
        # Extra buttons row
        extra_layout = QHBoxLayout()
        
        batch_rename_btn = QPushButton("Batch Rename")
        batch_rename_btn.clicked.connect(self.batch_rename)
        extra_layout.addWidget(batch_rename_btn)
        
        export_list_btn = QPushButton("Export List")
        export_list_btn.clicked.connect(self.export_file_list)
        extra_layout.addWidget(export_list_btn)
        
        file_details_btn = QPushButton("File Details")
        file_details_btn.clicked.connect(self.file_details)
        extra_layout.addWidget(file_details_btn)
        
        checksum_btn = QPushButton("Checksum")
        checksum_btn.clicked.connect(self.checksum)
        extra_layout.addWidget(checksum_btn)
        
        view_log_btn = QPushButton("View Log")
        view_log_btn.clicked.connect(self.view_log)
        extra_layout.addWidget(view_log_btn)
        
        terminal_btn = QPushButton("Terminal")
        terminal_btn.clicked.connect(self.open_terminal)
        extra_layout.addWidget(terminal_btn)
        
        sync_btn = QPushButton("Sync")
        sync_btn.clicked.connect(self.sync_folder)
        extra_layout.addWidget(sync_btn)
        
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(self.copy_files)
        extra_layout.addWidget(copy_btn)
        
        paste_btn = QPushButton("Paste")
        paste_btn.clicked.connect(self.paste_files)
        extra_layout.addWidget(paste_btn)

        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings)
        extra_layout.addWidget(settings_btn)

        self.transfers_btn = QPushButton("Transfers")
        self.transfers_btn.clicked.connect(self.show_transfers)
        extra_layout.addWidget(self.transfers_btn)

        main_layout.addLayout(button_layout)
        main_layout.addLayout(extra_layout)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        self.setLayout(main_layout)
        self.setWindowIcon(create_icon('folder'))

    # --- Themes ---
    def apply_theme(self):
        theme = self.theme_combo.currentText()
        if theme == "Default":
            self.setStyleSheet("")
        elif theme == "Light":
            self.setStyleSheet("background-color: #ffffff; color: black;")
        elif theme == "Dark":
            self.setStyleSheet("background-color: #2e2e2e; color: white;")
        elif theme == "Blue":
            self.setStyleSheet("background-color: #87CEFA; color: black;")
        elif theme == "Green":
            self.setStyleSheet("background-color: #90EE90; color: black;")
        elif theme == "Red":
            self.setStyleSheet("background-color: #FF6347; color: white;")
        elif theme == "Purple":
            self.setStyleSheet("background-color: #800080; color: white;")
        elif theme == "Orange":
            self.setStyleSheet("background-color: #FFA500; color: black;")
        elif theme == "Black":
            self.setStyleSheet("background-color: #000000; color: white;")
        elif theme == "Gray":
            self.setStyleSheet("background-color: #808080; color: white;")
        elif theme == "Teal":
            self.setStyleSheet("background-color: #008080; color: white;")

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.upload_dropped_files(files)

    def upload_dropped_files(self, files):
        device = self.get_selected_device()
        for file_path in files:
            file_name = os.path.basename(file_path)
            transfer_id = f"upload_{file_name}_{os.urandom(4).hex()}"
            self.transfer_window.add_transfer(transfer_id, f"Uploading {file_name}")
            self.set_processing_style(True)
            
            # Using AdbTransferWorker for upload
            from src.workers import AdbTransferWorker
            worker = AdbTransferWorker(["adb", "push", file_path, self.current_directory], device, self)
            
            worker.progress_update.connect(lambda msg, pct, spd, eta, tid=transfer_id: self.transfer_window.update_progress(tid, pct, spd))
            worker.finished_transfer.connect(lambda tid=transfer_id: self.on_transfer_finished(tid))
            worker.finished_transfer.connect(self.list_files)
            worker.error_occurred.connect(lambda err: QMessageBox.critical(self, "Error", f"Upload failed: {err}"))
            worker.start()

    def on_transfer_finished(self, transfer_id):
        self.transfer_window.mark_finished(transfer_id)
        if self.transfer_window.active_count == 0:
            self.set_processing_style(False)
            QMessageBox.information(self, "Finished", "Transfer completed!")

    def set_processing_style(self, active):
        if hasattr(self, 'transfers_btn'):
            if active:
                self.transfers_btn.setStyleSheet("background-color: green; color: white;")
            else:
                self.transfers_btn.setStyleSheet("")

    # --- Favorites ---
    def add_favorite(self):
        folder = self.current_directory
        if folder not in self.favorites:
            self.favorites.append(folder)
            self.favorites_combo.addItem(folder)
            QMessageBox.information(self, "Info", f"Added {folder} to favorites.")
        else:
            QMessageBox.information(self, "Info", "Folder already in favorites.")

    def remove_favorite(self):
        folder = self.favorites_combo.currentText()
        if folder in self.favorites:
            self.favorites.remove(folder)
            index = self.favorites_combo.currentIndex()
            self.favorites_combo.removeItem(index)
            QMessageBox.information(self, "Info", f"Removed {folder} from favorites.")
        else:
            QMessageBox.warning(self, "Warning", "No valid favorite selected.")

    def select_favorite(self, index):
        if index > 0:
            folder = self.favorites_combo.currentText()
            self.history.append(self.current_directory)
            self.current_directory = folder
            self.list_files()

    # --- Devices & List ---
    def get_selected_device(self):
        text = self.device_combo.currentText()
        if text and text != "No Device":
            return text
        return None

    def update_devices(self):
        devices = AdbManager.get_devices()
        current = self.device_combo.currentText()
        self.device_combo.clear()
        if devices:
            self.device_combo.addItems(devices)
            if current in devices:
                self.device_combo.setCurrentText(current)
        else:
            self.device_combo.addItem("No Device")

    def check_device(self):
        pass

    def list_files(self):
        self.progress_bar.setVisible(True)
        self.tree.clear()
        self.path_edit.setText(self.current_directory)
        device = self.get_selected_device()
        
        self.list_worker = FileListWorker(self.current_directory, device, self)
        self.list_worker.filesListed.connect(self.populate_file_tree)
        self.list_worker.errorOccurred.connect(self.on_list_error)
        self.list_worker.finished.connect(lambda: self.progress_bar.setVisible(False))
        self.list_worker.start()

    def populate_file_tree(self, files):
        for file in files:
            item = QTreeWidgetItem([file])
            if file.endswith('/'):
                item.setIcon(0, create_icon('folder'))
            else:
                item.setIcon(0, create_icon('file'))
            self.tree.addTopLevelItem(item)
        
    def on_list_error(self, error):
        QMessageBox.critical(self, "Error", error)

    # --- Navigation ---
    def on_path_changed(self):
        new_path = self.path_edit.text().strip()
        if new_path:
            self.history.append(self.current_directory)
            self.current_directory = new_path
            self.list_files()

    def on_item_double_clicked(self, item, column):
        name = item.text(0)
        if name.endswith("/"):
            self.history.append(self.current_directory)
            self.forward_history.clear()
            self.current_directory = os.path.join(self.current_directory, name).replace("\\", "/")
            self.list_files()
        else:
            # Add file open logic if needed
            pass

    def go_back(self):
        if self.history:
            self.forward_history.append(self.current_directory)
            self.current_directory = self.history.pop()
            self.list_files()

    def go_forward(self):
        if self.forward_history:
            self.history.append(self.current_directory)
            self.current_directory = self.forward_history.pop()
            self.list_files()
            
    def go_home(self):
        if self.current_directory != "/sdcard":
            self.history.append(self.current_directory)
            self.current_directory = "/sdcard"
            self.list_files()

    # --- Search ---
    def filter_files(self, text):
        search_term = text.lower()
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            item.setHidden(search_term not in item.text(0).lower())

    # --- Actions ---
    def download_file(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
            
        device = self.get_selected_device()
        files = [item.text(0) for item in selected]
        
        # Helper for common connection logic
        def setup_worker(worker, title):
            transfer_id = f"dl_{os.urandom(4).hex()}"
            self.transfer_window.add_transfer(transfer_id, title)
            self.set_processing_style(True)
            
            # Using new signal signature: msg, pct, speed, eta
            worker.progress_update.connect(lambda msg, pct, spd, eta, tid=transfer_id: self.transfer_window.update_progress(tid, pct, spd))
            worker.finished.connect(lambda tid=transfer_id: self.on_transfer_finished(tid))
            worker.start()

        if len(files) > 1:
            reply = QMessageBox.question(self, "Download", "Download as Zip?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                save_path, _ = QFileDialog.getSaveFileName(self, "Save Zip", "download.zip", "Zip (*.zip)")
                if save_path:
                    self.zip_worker = ZipWorker(files, self.current_directory, save_path, device, self)
                    setup_worker(self.zip_worker, "Downloading Zip")
                return

        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder")
        if folder:
            self.multi_dl_worker = MultiDownloadWorker(files, self.current_directory, folder, device, self)
            setup_worker(self.multi_dl_worker, "Downloading Files")

    def upload_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            self.upload_dropped_files([path])

    def delete_file(self):
        selected = self.tree.selectedItems()
        if not selected:
            return
        if QMessageBox.question(self, "Confirm", "Delete selected?") != QMessageBox.StandardButton.Yes:
            return
            
        device = self.get_selected_device()
        for item in selected:
            name = item.text(0)
            cmd = ["adb", "shell", "rm", "-rf", f"{self.current_directory}/{name}"]
            worker = AdbCommandWorker(cmd, device, self)
            worker.finished_with_output.connect(self.list_files)
            worker.start()

    def show_properties(self):
        selected = self.tree.selectedItems()
        if len(selected) != 1:
            return
        name = selected[0].text(0)
        device = self.get_selected_device()
        cmd = ["adb", "shell", "ls", "-l", f"{self.current_directory}/{name}"]
        worker = AdbCommandWorker(cmd, device, self)
        def show(output):
            GenericTextDialog("Properties", output, self).exec()
        worker.finished_with_output.connect(show)
        worker.start()

    def rename_file(self):
        selected = self.tree.selectedItems()
        if len(selected) != 1:
            return
        old_name = selected[0].text(0)
        new_name, ok = QInputDialog.getText(self, "Rename", "New Name:", text=old_name)
        if ok and new_name:
             device = self.get_selected_device()
             cmd = ["adb", "shell", "mv", f"{self.current_directory}/{old_name}", f"{self.current_directory}/{new_name}"]
             worker = AdbCommandWorker(cmd, device, self)
             worker.finished_with_output.connect(self.list_files)
             worker.start()

    # --- Dialogs ---
    def show_wifi_connection_dialog(self):
        WiFiConnectionDialog(self).exec()

    def open_settings(self):
        dlg = SettingsDialog(self.auto_refresh_devices, self.device_refresh_interval, self)
        if dlg.exec():
            self.auto_refresh_devices, self.device_refresh_interval = dlg.result_settings
            self.device_timer.setInterval(self.device_refresh_interval)

    def show_transfers(self):
        self.transfer_window.show()
        self.transfer_window.raise_()

    def open_terminal(self):
        TerminalDialog(AdbManager, self.get_selected_device(), self).show()
        
    def device_info(self):
        device = self.get_selected_device()
        worker = AdbCommandWorker(["adb", "shell", "getprop"], device, self)
        def show(output):
            GenericTextDialog("Device Info", output, self).exec()
        worker.finished_with_output.connect(show)
        worker.start()

    def view_log(self):
        try:
            with open("adb_file_browser.log", "r", encoding="utf-8") as f:
                content = f.read()
            GenericTextDialog("Log Viewer", content, self).exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open log: {e}")

    def create_new_folder(self):
        folder_name, ok = QInputDialog.getText(self, "New Folder", "Name:")
        if ok and folder_name:
             device = self.get_selected_device()
             cmd = ["adb", "shell", "mkdir", f"{self.current_directory}/{folder_name}"]
             worker = AdbCommandWorker(cmd, device, self)
             worker.finished_with_output.connect(self.list_files)
             worker.start()

    def install_apk(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select APK", filter="APK (*.apk)")
        if path:
            transfer_id = f"install_{os.urandom(4).hex()}"
            self.transfer_window.add_transfer(transfer_id, "Installing APK...")
            device = self.get_selected_device()
            worker = AdbCommandWorker(["adb", "install", path], device, self)
            worker.finished_with_output.connect(lambda: self.transfer_window.update_progress(transfer_id, 100))
            worker.start()

    def batch_rename(self):
        selected_items = self.tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select files to batch rename!")
            return
        
        base_name, ok = QInputDialog.getText(self, "Batch Rename", "Enter base name:")
        if not ok or not base_name:
            return
            
        start_index, ok = QInputDialog.getInt(self, "Batch Rename", "Start index:", 1, 1)
        if not ok:
            return
            
        device = self.get_selected_device()
        counter = start_index
        for item in selected_items:
            old_name = item.text(0)
            ext = os.path.splitext(old_name)[1]
            new_name = f"{base_name}_{counter}{ext}"
            
            cmd = ["adb", "shell", "mv", f"{self.current_directory}/{old_name}", f"{self.current_directory}/{new_name}"]
            worker = AdbCommandWorker(cmd, device, self)
            worker.start()
            counter += 1
        
        QTimer.singleShot(1000, self.list_files)

    def export_file_list(self):
        save_path, _ = QFileDialog.getSaveFileName(self, "Export List", "files.csv")
        if save_path:
            with open(save_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Name"])
                for i in range(self.tree.topLevelItemCount()):
                    writer.writerow([self.tree.topLevelItem(i).text(0)])

    def file_details(self):
        self.show_properties()

    def checksum(self):
        selected = self.tree.selectedItems()
        if len(selected) != 1: return
        name = selected[0].text(0)
        device = self.get_selected_device()
        worker = AdbCommandWorker(["adb", "shell", "md5sum", f"{self.current_directory}/{name}"], device, self)
        worker.finished_with_output.connect(lambda out: QMessageBox.information(self, "MD5", out))
        worker.start()

    def sync_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Sync Dest")
        if folder:
             device = self.get_selected_device()
             
             transfer_id = f"sync_{os.urandom(4).hex()}"
             self.transfer_window.add_transfer(transfer_id, "Syncing Folder...")
             self.set_processing_style(True)
             
             from src.workers import AdbTransferWorker
             worker = AdbTransferWorker(["adb", "pull", self.current_directory, folder], device, self)
             
             worker.progress_update.connect(lambda msg, pct, spd, eta, tid=transfer_id: self.transfer_window.update_progress(tid, pct, spd))
             worker.finished_transfer.connect(lambda tid=transfer_id: self.on_transfer_finished(tid))
             worker.error_occurred.connect(lambda err: QMessageBox.critical(self, "Error", f"Sync failed: {err}"))
             worker.start()

    def copy_files(self):
        selected = self.tree.selectedItems()
        self.copied_items = [(self.current_directory, item.text(0)) for item in selected]
        QMessageBox.information(self, "Copied", f"{len(self.copied_items)} files copied.")

    def paste_files(self):
        if not self.copied_items: return
        device = self.get_selected_device()
        for src_dir, name in self.copied_items:
            src = f"{src_dir}/{name}"
            dst = f"{self.current_directory}/{name}"
            worker = AdbCommandWorker(["adb", "shell", "cp", "-r", src, dst], device, self)
            worker.finished_with_output.connect(self.list_files)
            worker.start()
        self.copied_items = []

    def show_context_menu(self, pos):
        menu = QMenu()
        menu.addAction("Download", self.download_file)
        menu.addAction("Delete", self.delete_file)
        menu.addAction("Rename", self.rename_file)
        menu.addAction("Properties", self.show_properties)
        menu.exec(self.tree.viewport().mapToGlobal(pos))
