from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt

def create_icon(icon_type):
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setPen(Qt.GlobalColor.black)
    
    if icon_type == 'folder':
        painter.setBrush(QColor("yellow"))
        painter.drawRect(4, 8, 24, 16)
        painter.drawRect(4, 4, 24, 8)
    elif icon_type == 'file':
        painter.setBrush(Qt.GlobalColor.lightGray)
        painter.drawRect(4, 4, 24, 24)
        painter.drawRect(4, 4, 24, 8)
    elif icon_type == 'dark_mode':
        painter.setBrush(Qt.GlobalColor.black)
        painter.drawEllipse(8, 8, 16, 16)
    elif icon_type == 'light_mode':
        painter.setBrush(Qt.GlobalColor.white)
        painter.drawEllipse(8, 8, 16, 16)
        
    painter.end()
    return QIcon(pixmap)
