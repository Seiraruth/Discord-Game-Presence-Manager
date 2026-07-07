from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QDialog, QVBoxLayout
import os
from pathlib import Path

# Need to be able to load the style.qss
STYLE_PATH = Path(__file__).parent / "style.qss"

def load_global_stylesheet():
    try:
        with open(STYLE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""

class AccentDot(QWidget):
    """Tiny filled circle used as a status indicator in the title bar."""
    def __init__(self, color="#5865f2", size=6, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(size, size)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(self._color)
        p.drawEllipse(0, 0, self.width(), self.height())
        p.end()

class TitleBar(QWidget):
    def __init__(self, title="Discord Presence Manager", parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setObjectName("titleBarWidget")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 8, 0)
        layout.setSpacing(8)

        self.accent_dot = AccentDot(parent=self)
        layout.addWidget(self.accent_dot)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("titleBarLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        self.min_btn = QPushButton("—")
        self.min_btn.setObjectName("titleBarBtn")
        self.min_btn.setFixedSize(36, 28)
        self.min_btn.setCursor(Qt.PointingHandCursor)
        self.min_btn.clicked.connect(self.window().showMinimized)
        layout.addWidget(self.min_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("titleBarCloseBtn")
        self.close_btn.setFixedSize(36, 28)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.clicked.connect(self.window().close)
        layout.addWidget(self.close_btn)

        self.start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.start_pos is not None:
            delta = event.globalPos() - self.start_pos
            self.window().move(self.window().pos() + delta)
            self.start_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.start_pos = None

class AnimatedDialog(QDialog):
    """Base class for dialogs with frameless borders, custom title bar, and slide-up animations."""
    def __init__(self, title="", parent=None, show_minimize=False):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setStyleSheet(load_global_stylesheet())

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.title_bar = TitleBar(title, self)
        if not show_minimize:
            self.title_bar.min_btn.hide()
        self.main_layout.addWidget(self.title_bar)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(24, 24, 24, 32)
        self.content_layout.setSpacing(16)
        
        self.main_layout.addWidget(self.content_widget, 1)

    def showEvent(self, event):
        super().showEvent(event)
        # Slide-up + fade entrance
        self.setWindowOpacity(0.0)
        target_geo = self.geometry()
        start_geo = QRect(target_geo.x(), target_geo.y() + 15, target_geo.width(), target_geo.height())
        self.setGeometry(start_geo)

        self.fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self.fade_anim.setDuration(200)
        self.fade_anim.setStartValue(0.0)
        self.fade_anim.setEndValue(1.0)
        self.fade_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.slide_anim = QPropertyAnimation(self, b"geometry")
        self.slide_anim.setDuration(250)
        self.slide_anim.setStartValue(start_geo)
        self.slide_anim.setEndValue(target_geo)
        self.slide_anim.setEasingCurve(QEasingCurve.OutCubic)

        self.fade_anim.start()
        self.slide_anim.start()
