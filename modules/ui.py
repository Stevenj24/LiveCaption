from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget, QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from config import Config

class OverlayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.old_pos = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(Config.WINDOW_WIDTH, Config.WINDOW_HEIGHT)

        container = QWidget()
        self.setCentralWidget(container)
        container.setStyleSheet(f"""
            background-color: {Config.BG_COLOR};
            border-radius: 15px;
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 15, 20, 15)

        self.lbl_en = QLabel("Initialize Engine...")
        self.lbl_en.setFont(QFont(Config.FONT_FAMILY_EN, Config.FONT_SIZE_EN))
        self.lbl_en.setStyleSheet(f"color: {Config.COLOR_EN}; background: transparent;")
        self.lbl_en.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_en.setWordWrap(True)

        self.lbl_cn = QLabel("实时双语字幕")
        cn_font = QFont(Config.FONT_FAMILY_CN, Config.FONT_SIZE_CN)
        if Config.FONT_WEIGHT_CN == "Bold":
            cn_font.setBold(True)
        self.lbl_cn.setFont(cn_font)
        self.lbl_cn.setStyleSheet(f"color: {Config.COLOR_CN}; background: transparent;")
        self.lbl_cn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_cn.setWordWrap(True)

        layout.addWidget(self.lbl_en)
        layout.addWidget(self.lbl_cn)
        self._center_bottom()

    def _center_bottom(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = (screen.width() - self.width()) // 2
        y = screen.height() - self.height() - 100
        self.move(x, y)

    def update_en(self, text):
        """更新英文字幕，超长时截断显示最新部分"""
        text = self._truncate_text(text)
        self.lbl_en.setText(text)

    def update_cn(self, text):
        """更新中文字幕，超长时截断显示最新部分"""
        text = self._truncate_text(text)
        self.lbl_cn.setText(text)
    
    def _truncate_text(self, text: str) -> str:
        """截断过长文本，保留最新部分"""
        max_chars = Config.SUBTITLE_MAX_CHARS
        if len(text) > max_chars:
            # 保留后面的内容，前面加省略号
            return "..." + text[-(max_chars - 3):]
        return text

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def mouseDoubleClickEvent(self, event):
        QApplication.quit()