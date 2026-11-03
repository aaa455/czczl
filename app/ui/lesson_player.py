"""Reusable image/text cutscene player. All scene content comes from Lesson data."""
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Property, QPointF, QRectF, Qt, QPropertyAnimation, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (QCheckBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from app.lessons import resolve_image
from app.models import LearningScene, Lesson


def text_label(text: str, name: str = "body") -> QLabel:
    item = QLabel(text)
    item.setObjectName(name)
    item.setWordWrap(True)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return item


def control(text: str, callback: Callable, secondary: bool = False) -> QPushButton:
    item = QPushButton(text)
    item.setProperty("secondary", secondary)
    item.setMinimumHeight(42)
    item.clicked.connect(lambda checked=False: callback())
    return item


class SceneVisual(QWidget):
    """Renderer base: subclass paintEvent, use phase for animation; no private timers."""
    def __init__(self):
        super().__init__()
        self._phase = 0.0

    def get_phase(self) -> float:
        return self._phase

    def set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = Property(float, get_phase, set_phase)


class ImageTextVisual(SceneVisual):
    def __init__(self, scene: LearningScene, directory: Path, node_name: str):
        super().__init__()
        self.scene, self.node_name = scene, node_name
        path = resolve_image(directory, scene.image)
        self.pixmap = QPixmap(str(path)) if path is not None and path.is_file() else QPixmap()
        self.image_state = "已加载配图" if not self.pixmap.isNull() else (
            "配图暂不可用 · 使用占位画面" if scene.image else "图片占位 · 待补充素材")
        self.setAccessibleName(scene.image_alt + "；" + self.image_state)
        self.setMinimumSize(350, 270)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#efe5d0"))
        painter.save()
        # Ease in only the illustration: learning text stays visible and stable.
        if self.scene.transition == "fade":
            painter.setOpacity(min(1.0, 0.12 + self._phase * self.scene.duration_ms / 600))
        if not self.pixmap.isNull():
            # Fit the whole image; the modest animated zoom never crops its contents.
            bounds = QRectF(18, 18, self.width() - 36, self.height() - 82)
            size = self.pixmap.size().toSizeF()
            ratio = min(bounds.width() / size.width(), bounds.height() / size.height())
            ratio *= 0.96 + self._phase * 0.04
            target = QRectF(0, 0, size.width() * ratio, size.height() * ratio)
            target.moveCenter(bounds.center())
            painter.drawPixmap(target, self.pixmap, QRectF(self.pixmap.rect()))
        else:
            # Deliberately abstract artwork, not a pretend historical photograph.
            for row, color in [(0.52, "#d7c8a9"), (0.68, "#cbb894"), (0.86, "#bda780")]:
                ridge = QPainterPath(QPointF(-20, self.height()))
                ridge.lineTo(-20, self.height() * row)
                offset = self._phase * 12
                for i in range(10):
                    ridge.lineTo(i * self.width() / 8 - offset,
                                 self.height() * row - (55 if i % 2 else 0))
                ridge.lineTo(self.width() + 20, self.height())
                ridge.closeSubpath()
                painter.fillPath(ridge, QColor(color))
            painter.setPen(QColor("#9b7952"))
            painter.setFont(QFont("SimSun", 26))
            painter.drawText(QRectF(25, 25, self.width() - 50, 70),
                             Qt.AlignmentFlag.AlignCenter, "学习画面占位")
            painter.setFont(QFont("Microsoft YaHei UI", 13))
            painter.drawText(QRectF(25, 100, self.width() - 50, 60),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.node_name)
        painter.restore()
        painter.fillRect(QRectF(0, self.height() - 48, self.width(), 48), QColor("#e7dbc2"))
        painter.setPen(QColor("#705c41"))
        painter.setFont(QFont("Microsoft YaHei UI", 10))
        painter.drawText(QRectF(16, self.height() - 45, self.width() - 32, 42),
                         Qt.AlignmentFlag.AlignVCenter | Qt.TextFlag.TextWordWrap,
                         self.image_state)
        painter.end()


class SceneRendererRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[LearningScene, Path, str], SceneVisual]] = {}

    def register(self, kind: str, factory: Callable[[LearningScene, Path, str], SceneVisual]) -> None:
        if kind in self._factories:
            raise ValueError(f"分镜类型重复注册：{kind}")
        self._factories[kind] = factory

    def supports(self, kind: str) -> bool:
        return kind in self._factories

    def build(self, scene: LearningScene, directory: Path, node_name: str) -> SceneVisual:
        return self._factories[scene.kind](scene, directory, node_name)


def default_scene_renderers() -> SceneRendererRegistry:
    registry = SceneRendererRegistry()
    registry.register("image_text", ImageTextVisual)
    return registry


class LearningPlayer(QFrame):
    back_requested = Signal()
    quiz_requested = Signal()

    def __init__(self, lesson: Lesson, node_name: str, content_dir: Path,
                 renderers: SceneRendererRegistry | None = None):
        super().__init__()
        self.setObjectName("lessonPlayer")
        self.lesson, self.node_name, self.content_dir = lesson, node_name, content_dir
        self.renderers = renderers or default_scene_renderers()
        for scene in lesson.scenes:
            if not self.renderers.supports(scene.kind):
                raise ValueError(f"分镜缺少渲染器：{scene.kind}")
        self.index = 0
        self.visited: set[int] = set()
        self.disposed = False
        self.paused = False
        self.animation: QPropertyAnimation | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(15)
        heading = QHBoxLayout()
        heading.addWidget(text_label("先学习，再出发", "hero"), 1)
        self.counter = text_label("", "section")
        heading.addWidget(self.counter)
        heading.addWidget(control("返回路线", self.back_requested.emit, True))
        layout.addLayout(heading)
        layout.addWidget(text_label(node_name + "  ·  图文学习", "muted"))
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        scene_page = QWidget()
        scene_layout = QVBoxLayout(scene_page)
        scene_layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.visual_host = QStackedWidget()
        self.visual_host.setMinimumWidth(370)
        splitter.addWidget(self.visual_host)
        reading = QScrollArea()
        reading.setWidgetResizable(True)
        reading.setMinimumWidth(330)
        self.reading_content = QWidget()
        reading_layout = QVBoxLayout(self.reading_content)
        reading_layout.setContentsMargins(25, 15, 15, 20)
        reading_layout.setSpacing(20)
        self.scene_title = text_label("", "title")
        self.scene_text = text_label("", "lessonText")
        reading_layout.addWidget(text_label("本幕学习", "eyebrow"))
        reading_layout.addWidget(self.scene_title)
        reading_layout.addWidget(self.scene_text)
        reading_layout.addStretch()
        reading_layout.addWidget(text_label("可以暂停阅读，也可以手动切换分镜。", "muted"))
        reading.setWidget(self.reading_content)
        self.reading_scroll = reading
        splitter.addWidget(reading)
        splitter.setSizes([650, 430])
        scene_layout.addWidget(splitter, 1)
        self.pages.addWidget(scene_page)
        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary = QWidget()
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(45, 35, 45, 35)
        summary_layout.setSpacing(22)
        summary_layout.addWidget(text_label("本段学习小结", "eyebrow"))
        summary_layout.addWidget(text_label("带着收获，开始检验", "hero"))
        summary_layout.addWidget(text_label(lesson.summary, "lessonText"))
        summary_layout.addWidget(text_label("知识检验可以帮助你发现还需要回顾的内容。", "muted"))
        summary_layout.addStretch()
        summary_layout.addWidget(control("重新观看本段", self.replay, True))
        self.quiz_button = control("已学习，开始答题", self.request_quiz)
        summary_layout.addWidget(self.quiz_button)
        summary_scroll.setWidget(summary)
        self.pages.addWidget(summary_scroll)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        controls = QHBoxLayout()
        self.previous_button = control("上一幕", self.previous_scene, True)
        self.pause_button = control("暂停", self.toggle_pause, True)
        self.next_button = control("下一幕", self.next_scene)
        self.auto = QCheckBox("自动翻页")
        self.auto.setChecked(True)
        self.playback_status = text_label("可随时暂停或手动翻页", "muted")
        controls.addWidget(self.previous_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.auto)
        controls.addWidget(self.playback_status, 1)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)

    def start(self) -> None:
        self._show_scene(0)

    def _stop_animation(self) -> None:
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None

    def _show_scene(self, index: int) -> None:
        if self.disposed:
            return
        self._stop_animation()
        self.index = index
        self.visited.add(index)
        self.pages.setCurrentIndex(0)
        scene = self.lesson.scenes[index]
        self.scene_title.setText(scene.title)
        self.scene_text.setText(scene.text)
        self.reading_scroll.verticalScrollBar().setValue(0)
        old = self.visual_host.currentWidget()
        if old is not None:
            self.visual_host.removeWidget(old)
            old.deleteLater()
        self.visual = self.renderers.build(scene, self.content_dir, self.node_name)
        self.visual_host.addWidget(self.visual)
        self.visual_host.setCurrentWidget(self.visual)
        self.counter.setText(f"第 {index + 1} 幕 / 共 {len(self.lesson.scenes)} 幕")
        self.previous_button.setEnabled(index > 0)
        self.pause_button.setEnabled(True)
        self.next_button.setEnabled(True)
        self.next_button.setText("查看学习小结" if index == len(self.lesson.scenes) - 1 else "下一幕")
        self.animation = QPropertyAnimation(self.visual, b"phase", self)
        self.animation.setDuration(scene.duration_ms)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self._frame_changed)
        self.animation.finished.connect(self._scene_finished)
        self.animation.start()
        if self.paused:
            self.animation.pause()
        self._update_pause_text()
        self._frame_changed(0.0)

    def _frame_changed(self, value) -> None:
        self.progress.setValue(round(1000 * (self.index + float(value)) / len(self.lesson.scenes)))

    def _scene_finished(self) -> None:
        if not self.disposed and self.auto.isChecked() and not self.paused:
            self.next_scene()
        elif not self.disposed:
            self.playback_status.setText("本幕播放结束，可点击下一幕")

    def next_scene(self) -> None:
        if self.disposed or self.pages.currentIndex() != 0:
            return
        if self.index + 1 < len(self.lesson.scenes):
            self._show_scene(self.index + 1)
        else:
            self._show_summary()

    def previous_scene(self) -> None:
        if not self.disposed:
            if self.pages.currentIndex() == 1:
                self._show_scene(self.index)
            elif self.index > 0:
                self._show_scene(self.index - 1)

    def _show_summary(self) -> None:
        if len(self.visited) != len(self.lesson.scenes):
            return
        self._stop_animation()
        self.pages.setCurrentIndex(1)
        self.counter.setText("学习小结")
        self.progress.setValue(1000)
        self.previous_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self.playback_status.setText("可以重看，或确认学习后开始答题")

    def request_quiz(self) -> None:
        if not self.disposed and self.pages.currentIndex() == 1 and len(self.visited) == len(self.lesson.scenes):
            self.quiz_requested.emit()

    def replay(self) -> None:
        self.visited.clear()
        self.paused = False
        self._show_scene(0)

    def _update_pause_text(self) -> None:
        self.pause_button.setText("继续播放" if self.paused else "暂停")
        self.playback_status.setText("已暂停 · 可以手动翻页" if self.paused else "可随时暂停或手动翻页")

    def pause(self) -> None:
        if self.disposed or self.pages.currentIndex() != 0:
            return
        self.paused = True
        if self.animation is not None and self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.pause()
        self._update_pause_text()

    def toggle_pause(self) -> None:
        if not self.paused:
            self.pause()
            return
        self.paused = False
        if self.animation is not None and self.animation.state() == QPropertyAnimation.State.Paused:
            self.animation.resume()
        self._update_pause_text()

    def stop(self) -> None:
        self.disposed = True
        self._stop_animation()

    def hideEvent(self, event):
        self.pause()
        super().hideEvent(event)
