"""Replaceable PNG badge export using Qt drawing, without external assets."""
from datetime import date
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

from app.models import LearningSummary


class BadgeExporter(Protocol):
    def export(self, path: Path, name: str, summary: LearningSummary) -> None: ...


class PngBadgeExporter:
    def export(self, path: Path, name: str, summary: LearningSummary) -> None:
        if summary.completed_nodes != summary.total_nodes:
            raise ValueError("完成全部学习节点后才能领取徽章")
        image = QImage(900, 1120, QImage.Format.Format_ARGB32)
        image.fill(QColor("#f6eedc"))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#92362e"), 3))
        painter.drawRect(35, 35, 830, 1050)
        painter.setPen(QPen(QColor("#bc9a67"), 1))
        painter.drawRect(49, 49, 802, 1022)

        def text(y: int, value: str, size: int, color: str = "#4f3c2d"):
            painter.setPen(QColor(color))
            painter.setFont(QFont("Microsoft YaHei UI", size))
            painter.drawText(QRectF(75, y, 750, 78), Qt.AlignmentFlag.AlignCenter, value)

        text(100, "足迹长征", 39, "#91372e")
        text(185, "学习纪念徽章", 20, "#93754c")
        text(320, (name.strip() or "长征学习者")[:12], 32)
        text(420, "循足迹 · 知历史 · 悟精神", 21)
        text(555, f"完成节点   {summary.completed_nodes} / {summary.total_nodes}", 23)
        text(635, f"首次答对   {summary.first_correct} / {summary.total_questions}", 23)
        text(715, f"已掌握题目   {summary.mastered_questions} / {summary.total_questions}", 23)
        text(865, "赓续长征精神，智创青春新程", 21, "#91372e")
        text(945, date.today().isoformat(), 16, "#93754c")
        painter.end()
        if not image.save(str(path), "PNG"):
            raise OSError("徽章图片保存失败，请检查目标目录权限")
