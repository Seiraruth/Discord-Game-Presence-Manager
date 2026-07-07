import sys
from PyQt5.QtWidgets import QApplication, QListWidget, QListWidgetItem, QDialog, QVBoxLayout, QWidget, QStyledItemDelegate
from PyQt5.QtCore import QSize, Qt
from PyQt5.QtGui import QPainter, QColor

class MyDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setBrush(QColor("red"))
        # Draw exactly the option.rect to see the cell size
        painter.drawRect(option.rect.adjusted(0, 0, -1, -1))
        painter.restore()

class TestWin(QDialog):
    def __init__(self):
        super().__init__()
        self.resize(800, 400)
        lay = QVBoxLayout(self)
        self.list = QListWidget()
        self.list.setViewMode(QListWidget.IconMode)
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(10)
        self.list.setItemDelegate(MyDelegate(self.list))
        for i in range(20):
            self.list.addItem(f"Item {i}")
        lay.addWidget(self.list)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        w = self.list.viewport().width()
        spacing = self.list.spacing()
        min_w = 178
        if w > 0:
            cols = max(1, w // (min_w + spacing))
            cell_w = (w // cols) - spacing
            self.list.setGridSize(QSize(cell_w, 200))
            print(f"Viewport: {w}, Cols: {cols}, Cell: {cell_w}, Total row width: {cols * (cell_w + spacing)}")

app = QApplication(sys.argv)
win = TestWin()
win.show()
# We don't want to run exec_ because it will block. We just want to see the print output from resize.
win.resize(800, 400)
win.resizeEvent(None)
app.processEvents()
