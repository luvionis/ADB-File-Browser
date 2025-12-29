from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QProgressBar, QHBoxLayout, 
    QListWidget, QListWidgetItem, QPushButton, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from datetime import datetime

class TransferItemWidget(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5) # Add some padding
        
        top_row = QHBoxLayout()
        self.label = QLabel(title)
        self.label.setStyleSheet("font-weight: bold; font-size: 13px;")
        top_row.addWidget(self.label)
        
        self.speed_label = QLabel("Waiting...")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        top_row.addWidget(self.speed_label)
        layout.addLayout(top_row)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setStyleSheet("QProgressBar { height: 16px; border-radius: 4px; } QProgressBar::chunk { background-color: #3b82f6; border-radius: 4px; }")
        layout.addWidget(self.progress_bar)
        
        self.details_label = QLabel("") 
        self.details_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.details_label)
        
        self.setLayout(layout)

    def set_progress(self, value, speed="", details=""):
        self.progress_bar.setValue(value)
        if speed:
            self.speed_label.setText(speed)
        if details:
            self.details_label.setText(details)
            
class HistoryItemWidget(QWidget):
    def __init__(self, title, timestamp, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        
        name_label = QLabel(title)
        name_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(name_label)
        layout.addStretch()
        
        time_label = QLabel(timestamp)
        time_label.setStyleSheet("color: gray;")
        layout.addWidget(time_label)
        self.setLayout(layout)

class TransferWindow(QWidget):
    transfers_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Transfers")
        self.resize(500, 400)
        
        layout = QVBoxLayout()
        
        self.tabs = QTabWidget()
        self.active_list = QListWidget()
        self.history_list = QListWidget()
        
        self.tabs.addTab(self.active_list, "Active")
        self.tabs.addTab(self.history_list, "History")
        
        layout.addWidget(self.tabs)
        
        btn_layout = QHBoxLayout()
        self.clear_history_btn = QPushButton("Clear History")
        self.clear_history_btn.clicked.connect(self.history_list.clear)
        btn_layout.addWidget(self.clear_history_btn)
        
        self.hide_btn = QPushButton("Hide")
        self.hide_btn.clicked.connect(self.hide)
        btn_layout.addWidget(self.hide_btn)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.transfers = {} # id -> (item, widget) in active list
        self.active_count = 0

    def add_transfer(self, transfer_id, title):
        # Switch to active tab
        self.tabs.setCurrentIndex(0)
        
        item = QListWidgetItem()
        widget = TransferItemWidget(title)
        item.setSizeHint(widget.sizeHint())
        
        self.active_list.addItem(item)
        self.active_list.setItemWidget(item, widget)
        
        self.transfers[transfer_id] = (item, widget)
        self.active_count += 1
        
        self.show()
        self.raise_()

    def update_progress(self, transfer_id, value, speed=""):
        if transfer_id in self.transfers:
            item, widget = self.transfers[transfer_id]
            # If we had bytes info we could pass it to details
            widget.set_progress(value, speed)

    def mark_finished(self, transfer_id):
        if transfer_id in self.transfers:
            item, widget = self.transfers[transfer_id]
            widget.set_progress(100, "Completed")
            
            # Move to history
            title = widget.label.text()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Remove from active
            row = self.active_list.row(item)
            self.active_list.takeItem(row)
            del self.transfers[transfer_id]
            
            # Add to history
            h_item = QListWidgetItem()
            h_widget = HistoryItemWidget(title, timestamp)
            h_item.setSizeHint(h_widget.sizeHint())
            self.history_list.insertItem(0, h_item)
            self.history_list.setItemWidget(h_item, h_widget)
            
            self.active_count -= 1
            if self.active_count <= 0:
                self.active_count = 0
                self.transfers_finished.emit()
                self.hide()

    def closeEvent(self, event):
        self.hide()
        event.ignore()
