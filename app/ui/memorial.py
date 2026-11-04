"""Full-window flower offering and martyr memorial view."""
import random
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (QDialog, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget)


class _FlowerBouquet(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(48, 48)
        self.setAccessibleName("献上的花束")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#647b56"), 1.7))
        painter.drawLine(23, 23, 16, 43)
        painter.drawLine(25, 21, 25, 43)
        painter.drawLine(27, 23, 34, 43)
        painter.drawEllipse(15, 31, 8, 4)
        painter.drawEllipse(27, 34, 8, 4)
        painter.setPen(QPen(QColor("#a48353"), 1.2))
        painter.drawLine(16, 43, 34, 43)
        for center, color in [((15, 14), "#a8473c"), ((24, 10), "#c6944d"), ((33, 14), "#a8473c")]:
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(QColor(color))
            cx, cy = center
            for dx, dy in [(0, -4), (4, -1), (2, 3), (-2, 3), (-4, -1)]:
                painter.drawEllipse(cx + dx - 2, cy + dy - 2, 4, 4)
            painter.setBrush(QColor("#e4c37b"))
            painter.drawEllipse(cx - 2, cy - 2, 4, 4)
        painter.end()


class MemorialWindow(QDialog):
    def __init__(self, martyrs: list[dict], portrait_dir: Path, parent: QWidget):
        super().__init__(parent)
        self.martyrs = martyrs
        self.portrait_dir = portrait_dir
        self.setObjectName("memorialWindow")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setGeometry(parent.frameGeometry())
        self.background = QPixmap(str(portrait_dir.parents[1] / "images" / "long-march-landscape.png"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 22, 34, 24)
        layout.setSpacing(15)
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("长征英烈 · 献花纪念")
        title.setObjectName("memorialWindowTitle")
        title_box.addWidget(title)
        self.progress_label = QLabel("全部学习节点已完成")
        self.progress_label.setObjectName("memorialWindowProgress")
        title_box.addWidget(self.progress_label)
        header.addLayout(title_box)
        header.addStretch()
        self.return_button = QPushButton("返回路线")
        self.return_button.setObjectName("memorialReturnButton")
        self.return_button.clicked.connect(self.dismiss)
        header.addWidget(self.return_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        self.invitation = QLabel("谨以一束花，向长征途中牺牲的英烈致敬")
        self.invitation.setObjectName("memorialInvitation")
        self.invitation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.invitation.setWordWrap(True)
        layout.addWidget(self.invitation)

        offering = QHBoxLayout()
        offering.addStretch()
        self.flower = _FlowerBouquet()
        self.flower_effect = QGraphicsOpacityEffect(self.flower)
        self.flower_effect.setOpacity(0.0)
        self.flower.setGraphicsEffect(self.flower_effect)
        self.flower.hide()
        offering.addWidget(self.flower)
        self.flower_button = QPushButton("献上一束花")
        self.flower_button.setObjectName("memorialFlowerButton")
        self.flower_button.setMinimumSize(220, 46)
        self.flower_button.clicked.connect(self.reveal)
        offering.addWidget(self.flower_button)
        offering.addStretch()
        layout.addLayout(offering)

        self.content = QWidget()
        content_layout = QHBoxLayout(self.content)
        content_layout.setContentsMargins(10, 0, 10, 0)
        content_layout.setSpacing(30)
        self.portrait = QLabel()
        self.portrait.setObjectName("memorialPortrait")
        self.portrait.setFixedSize(280, 420)
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.portrait.setScaledContents(True)
        content_layout.addWidget(self.portrait, 0, Qt.AlignmentFlag.AlignVCenter)
        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 16, 0)
        details.setSpacing(10)
        self.name_label = QLabel()
        self.name_label.setObjectName("memorialName")
        self.name_label.setWordWrap(True)
        details.addWidget(self.name_label)
        self.years_label = QLabel()
        self.years_label.setObjectName("memorialYears")
        details.addWidget(self.years_label)
        self.role_label = QLabel()
        self.role_label.setObjectName("memorialRole")
        self.role_label.setWordWrap(True)
        details.addWidget(self.role_label)
        self.biography_label = QLabel()
        self.biography_label.setObjectName("memorialBiography")
        self.biography_label.setWordWrap(True)
        self.biography_label.setMinimumHeight(100)
        self.biography_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        details.addWidget(self.biography_label)
        details.addStretch()
        self.image_note = QLabel("AI 创作的纪念形象，并非烈士真实肖像")
        self.image_note.setObjectName("memorialImageNote")
        details.addWidget(self.image_note)
        content_layout.addLayout(details, 1)
        self.opacity = QGraphicsOpacityEffect(self.content)
        self.opacity.setOpacity(0.0)
        self.content.setGraphicsEffect(self.opacity)
        self.content.hide()
        layout.addWidget(self.content, 1)

        self.setWindowOpacity(0.0)
        self.animation: QPropertyAnimation | None = None
        self.flower_animation: QPropertyAnimation | None = None
        self.dismiss_animation: QPropertyAnimation | None = None

    def paintEvent(self, event):
        painter = QPainter(self)
        if not self.background.isNull():
            painter.drawPixmap(self.rect(), self.background)
        painter.fillRect(self.rect(), QColor(28, 35, 31, 166))

    def reveal(self) -> None:
        martyr = random.choice(self.martyrs)
        image_name = "male-red-army.png" if martyr["gender"] == "male" else "female-red-army.png"
        pixmap = QPixmap(str(self.portrait_dir / image_name))
        self.portrait.setPixmap(pixmap)
        self.portrait.setAccessibleName(f"{martyr['name']}的AI纪念形象")
        self.name_label.setText(martyr["name"])
        self.years_label.setText(martyr["years"])
        self.role_label.setText(martyr["role"])
        self.biography_label.setText(martyr["biography"])
        self.invitation.setText("献花礼成 · 瞻仰英烈")
        self.flower_button.setText("再献一束花")
        self.content.show()
        self.flower.show()
        if self.flower_animation is not None:
            self.flower_animation.stop()
        self.flower_effect.setOpacity(0.0)
        self.flower_animation = QPropertyAnimation(self.flower_effect, b"opacity", self)
        self.flower_animation.setDuration(550)
        self.flower_animation.setStartValue(0.0)
        self.flower_animation.setEndValue(1.0)
        self.flower_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.flower_animation.start()
        if self.animation is not None:
            self.animation.stop()
        self.opacity.setOpacity(0.0)
        self.animation = QPropertyAnimation(self.opacity, b"opacity", self)
        self.animation.setDuration(900)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.start()

    def dismiss(self) -> None:
        self.dismiss_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self.dismiss_animation.setDuration(260)
        self.dismiss_animation.setStartValue(self.windowOpacity())
        self.dismiss_animation.setEndValue(0.0)
        self.dismiss_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.dismiss_animation.finished.connect(self.accept)
        self.dismiss_animation.start()
