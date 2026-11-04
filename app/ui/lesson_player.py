"""Full-window learning scenes with a reusable, translucent reading overlay."""
from collections.abc import Callable
import math
from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QEvent, QPoint, QPointF, QRectF, Qt,
                           QPropertyAnimation, QTimer, Signal)
from PySide6.QtGui import (QColor, QImage, QLinearGradient, QPainter,
                          QPainterPath, QPen, QPixmap, QShortcut, QKeySequence)
from PySide6.QtWidgets import (QFrame, QGraphicsBlurEffect, QGraphicsDropShadowEffect,
    QGraphicsPixmapItem, QGraphicsScene, QLabel, QPushButton, QScrollArea,
    QStackedWidget, QVBoxLayout, QWidget)

from app.lessons import resolve_image
from app.models import LearningScene, Lesson


class SceneVisual(QWidget):
    """Renderer extension: paint over the whole widget and use the shared phase clock."""
    def __init__(self):
        super().__init__()
        self._phase = 0.0

    def get_phase(self) -> float:
        return self._phase

    def set_phase(self, value: float) -> None:
        self._phase = value
        self.update()

    phase = Property(float, get_phase, set_phase)

    def background_opacity(self) -> float:
        return 1.0

    def backdrop_image(self) -> QImage:
        image = self.grab().toImage()
        # All glass geometry is in logical window coordinates, including on HiDPI.
        image.setDevicePixelRatio(1.0)
        return image.scaled(self.size(), Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)


class ImageTextVisual(SceneVisual):
    def __init__(self, scene: LearningScene, directory: Path, node_name: str):
        super().__init__()
        self.scene, self.node_name = scene, node_name
        path = resolve_image(directory, scene.image)
        self.pixmap = QPixmap(str(path)) if path is not None and path.is_file() else QPixmap()
        self.image_state = "已加载配图" if not self.pixmap.isNull() else (
            "配图暂不可用 · 使用占位画面" if scene.image else "图片占位 · 待补充素材")
        self.setAccessibleName(scene.image_alt + "；" + self.image_state)

    def background_opacity(self) -> float:
        if self.scene.transition == "fade" and not getattr(self, "entrance_prepared", False):
            return min(1.0, 0.12 + self._phase * self.scene.duration_ms / 600)
        return 1.0

    def backdrop_image(self) -> QImage:
        # Render the final background once, independent of the live fade clock.
        image = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        self._paint_background(painter)
        painter.end()
        return image

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#a4afa2"))
        painter.setOpacity(self.background_opacity())
        self._paint_background(painter)
        painter.end()

    def _paint_background(self, painter: QPainter) -> None:
        painter.setRenderHints(QPainter.RenderHint.Antialiasing |
                               QPainter.RenderHint.SmoothPixmapTransform)
        if not self.pixmap.isNull():
            # Deliberately stretch to the complete client area, as requested.
            painter.drawPixmap(QRectF(self.rect()), self.pixmap, QRectF(self.pixmap.rect()))
        else:
            sky = QLinearGradient(0, 0, self.width() * .5, self.height())
            sky.setColorAt(0, QColor("#ddd7bc"))
            sky.setColorAt(.45, QColor("#a4afa2"))
            sky.setColorAt(1, QColor("#506e65"))
            painter.fillRect(self.rect(), sky)
            # Abstract placeholder scenery; no titles or image-state banners over it.
            for base, amplitude, phase, color in [
                (.38, .065, 1.8, "#96a398"), (.45, .09, 4.4, "#80958b"),
                (.53, .11, 2.1, "#68857b"), (.66, .13, 5.2, "#506f65"),
                (.8, .15, .9, "#34584f"),
            ]:
                ridge = QPainterPath(QPointF(-10, self.height()))
                for x in range(-10, self.width() + 11, 4):
                    u = x / max(1, self.width()) * 1920
                    wave = (.54 * math.sin(u / 180 + phase) +
                            .24 * math.sin(u / 76 + phase * 2) +
                            .13 * math.sin(u / 32 + phase * .7))
                    ridge.lineTo(x, self.height() * (base + amplitude * wave))
                ridge.lineTo(self.width() + 10, self.height())
                ridge.closeSubpath()
                painter.fillPath(ridge, QColor(color))


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


class GlassTextPanel(QWidget):
    """Full-width smoky glass, fading from a dark centre to transparent sides."""
    activated = Signal()
    EDGE_ALPHA = 8
    CENTRE_ALPHA = 116

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("glassPanel")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._backdrop = QPixmap()
        self._backdrop_offset = QPoint()
        self._backdrop_visual: SceneVisual | None = None
        self._type_size: int | None = None
        self._press_position = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 20, 28, 20)
        layout.setSpacing(8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.text = QLabel()
        self.text.setObjectName("cinematicText")
        self.text.setWordWrap(True)
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll.setWidget(self.text)
        layout.addWidget(self.scroll, 1)
        self.hint = QLabel()
        self.hint.setObjectName("cinematicHint")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setTextFormat(Qt.TextFormat.PlainText)
        self.hint.hide()
        layout.addWidget(self.hint)
        for widget in (self, self.scroll.viewport(), self.text, self.hint):
            widget.installEventFilter(self)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 42))
        self.setGraphicsEffect(shadow)
        self.setToolTip("点击翻页；空格暂停 / 继续；左右方向键切换；Esc退出学习")

    def set_hint(self, text: str) -> None:
        self.hint.setText(text)
        self.hint.setVisible(bool(text))

    def set_type_size(self, size: int) -> None:
        if self._type_size == size:
            return
        self._type_size = size
        self.setStyleSheet(
            "QWidget#glassPanel, QScrollArea, QScrollArea > QWidget > QWidget "
            "{ background: transparent; border: none; }"
            f"QLabel#cinematicText {{ background: transparent; color: #f5f4e6; font-size: {size}px; }}"
            f"QLabel#cinematicHint {{ background: transparent; color: #f5f4e6; font-size: {max(12, size - 5)}px; }}")

    def _gradient(self, rgb: tuple[int, int, int], edge: int, centre: int) -> QLinearGradient:
        gradient = QLinearGradient(0, 0, max(1, self.width() - 1), 0)
        for step in range(17):
            position = step / 16
            weight = math.sin(math.pi * position) ** 1.45
            gradient.setColorAt(position, QColor(*rgb, round(edge + (centre - edge) * weight)))
        return gradient

    def refresh_backdrop(self, visual: SceneVisual) -> None:
        # Use a final background in logical coordinates, not a partially faded
        # screen grab. The painter follows the live fade without rebuilding blur.
        padding = 32
        crop = self.geometry().adjusted(-padding, -padding, padding, padding).intersected(visual.rect())
        if crop.isEmpty():
            return
        frame = visual.backdrop_image()
        frame.setDevicePixelRatio(1.0)
        cropped = frame.copy(crop)
        # Blur a smaller crop; its radius is scaled to preserve the visual size.
        scale = min(1.0, 640 / cropped.width())
        source = QPixmap.fromImage(cropped.scaled(
            max(1, round(cropped.width() * scale)), max(1, round(cropped.height() * scale)),
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation))
        scene = QGraphicsScene()
        item = QGraphicsPixmapItem(source)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(22 * scale)
        blur.setBlurHints(QGraphicsBlurEffect.BlurHint.QualityHint)
        item.setGraphicsEffect(blur)
        scene.addItem(item)
        scene.setSceneRect(QRectF(source.rect()))
        result = QImage(source.size(), QImage.Format.Format_ARGB32_Premultiplied)
        result.fill(Qt.GlobalColor.transparent)
        painter = QPainter(result)
        scene.render(painter, QRectF(result.rect()), scene.sceneRect())
        painter.end()
        # Fade the blur along with the tint so the edges blend into the scenery.
        backdrop = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        backdrop.fill(Qt.GlobalColor.transparent)
        painter = QPainter(backdrop)
        target = QRectF(crop.translated(-self.pos()))
        painter.drawImage(target, result, QRectF(result.rect()))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(backdrop.rect(), self._gradient((255, 255, 255), 60, 255))
        painter.end()
        self._backdrop = QPixmap.fromImage(backdrop)
        self._backdrop_offset = QPoint()
        self._backdrop_visual = visual
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self._backdrop.isNull():
            if self._backdrop_visual is not None:
                painter.setOpacity(self._backdrop_visual.background_opacity())
            painter.drawPixmap(self._backdrop_offset, self._backdrop)
            painter.setOpacity(1.0)
        painter.fillRect(self.rect(), self._gradient((20, 36, 31), self.EDGE_ALPHA, self.CENTRE_ALPHA))
        painter.setPen(QPen(self._gradient((247, 246, 229), 8, 51), 1))
        painter.drawLine(QPointF(0, .5), QPointF(self.width(), .5))
        painter.setPen(QPen(self._gradient((247, 246, 229), 4, 26), 1))
        painter.drawLine(QPointF(0, self.height() - .5), QPointF(self.width(), self.height() - .5))

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            self._press_position = event.globalPosition().toPoint()
        elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._press_position is not None:
                distance = (event.globalPosition().toPoint() - self._press_position).manhattanLength()
                self._press_position = None
                if distance <= 6:
                    self.activated.emit()
                    return True
        return super().eventFilter(watched, event)


class LearningEntrance(QWidget):
    """Route snapshot fades through a soft shade into the live learning background."""
    progress_changed = Signal(float)
    resume_requested = Signal()
    DURATION_MS = 850

    def __init__(self, snapshot: QPixmap, parent: QWidget):
        super().__init__(parent)
        self.snapshot = snapshot
        self._progress = 0.0
        self.paused = False
        self.panel_snapshot = QPixmap()
        self.panel_bounds = QRectF()

    def set_panel(self, snapshot: QPixmap, bounds: QRectF) -> None:
        self.panel_snapshot, self.panel_bounds = snapshot, bounds
        self.update()

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        self._progress = value
        self.progress_changed.emit(value)
        self.update()

    progress = Property(float, get_progress, set_progress)

    def paintEvent(self, event):
        elapsed = self._progress * self.DURATION_MS
        reveal = max(0.0, min(1.0, (elapsed - 180) / 450))
        reveal = QEasingCurve(QEasingCurve.Type.InOutCubic).valueForProgress(reveal)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.setOpacity(1 - reveal)
        painter.drawPixmap(QRectF(self.rect()), self.snapshot, QRectF(self.snapshot.rect()))
        painter.setOpacity(1)
        shade = .3 * min(1.0, elapsed / 180) * (1 - reveal)
        painter.fillRect(self.rect(), QColor(12, 22, 18, round(255 * shade)))
        text_progress = max(0.0, min(1.0, (elapsed - 500) / 350))
        text_progress = QEasingCurve(QEasingCurve.Type.OutCubic).valueForProgress(text_progress)
        painter.setOpacity(text_progress)
        if not self.panel_snapshot.isNull():
            target = self.panel_bounds.translated(0, round(12 * (1 - text_progress)))
            painter.drawPixmap(target, self.panel_snapshot, QRectF(self.panel_snapshot.rect()))
        if self.paused:
            painter.setOpacity(1)
            painter.setPen(QColor("#fffdf2"))
            painter.drawText(QRectF(0, self.height() - 44, self.width(), 30),
                             Qt.AlignmentFlag.AlignCenter, "已暂停 · 点击画面或按空格继续")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.resume_requested.emit()


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
        self.summary_visible = False
        self.animation: QPropertyAnimation | None = None
        self.entering = False
        self.entrance_animation: QPropertyAnimation | None = None
        self.entrance: LearningEntrance | None = None
        self._entrance_offset = 0
        self._entrance_text_opacity = 1.0
        self._glass_cache_key = None
        self.visual_host = QStackedWidget(self)
        self.glass = GlassTextPanel(self)
        self.scene_text = self.glass.text
        self.reading_scroll = self.glass.scroll
        self.glass.activated.connect(self.activate_text)
        self.exit_button = QPushButton("退出  ×", self)
        self.exit_button.setObjectName("lessonExit")
        self.exit_button.setAccessibleName("退出学习，返回路线")
        self.exit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.exit_button.clicked.connect(self.back_requested.emit)
        self._blur_timer = QTimer(self)
        self._blur_timer.setSingleShot(True)
        self._blur_timer.timeout.connect(self._refresh_glass)
        self._shortcuts = []
        for key, callback in [("Escape", self.back_requested.emit), ("Space", self.toggle_pause),
                              ("Right", self.next_scene), ("Left", self.previous_scene),
                              ("Return", self.activate_text), ("Enter", self.activate_text),
                              ("R", self.replay)]:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.setAutoRepeat(False)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_overlays()

    def _layout_overlays(self) -> None:
        self.visual_host.setGeometry(self.rect())
        self.visual_host.layout().activate()
        if self.entrance is not None:
            self.entrance.setGeometry(self.rect())
        width = self.width()
        # Keep the original reading measure and height while extending only the glass.
        reading_width = round(width * .69)
        text_margin = (width - reading_width) // 2 + 28
        self.glass.layout().setContentsMargins(text_margin, 20, text_margin, 20)
        font_size = max(17, min(31, round(self.width() / 62)))
        self.glass.set_type_size(font_size)
        text_height = self.scene_text.heightForWidth(max(1, reading_width - 56))
        hint_height = 28 if self.glass.hint.text() else 0
        height = min(round(self.height() * .30), max(128, text_height + 48 + hint_height))
        bottom = max(24, round(self.height() * .065))
        self.glass.setGeometry((self.width() - width) // 2,
                               self.height() - bottom - height,
                               width, height)
        self.glass.layout().activate()
        margin = max(22, round(self.width() * .022))
        self.exit_button.setGeometry(self.width() - margin - 96, margin, 96, 40)
        self.glass.raise_()
        self.exit_button.raise_()
        if not self.disposed:
            # The visible frame must never contain the previous scene's crop or
            # an old-sized panel. A queued pass only settles child layout events.
            self._refresh_glass()
            self._blur_timer.start(0)

    def _refresh_glass(self) -> None:
        if not self.disposed and hasattr(self, "visual") and self.visual.width() > 0:
            key = (self.visual, self.visual.size(), self.glass.geometry())
            if key != self._glass_cache_key:
                self.glass.refresh_backdrop(self.visual)
                self._glass_cache_key = key
            if self.entering and self.entrance is not None:
                self.entrance.set_panel(self.glass.grab(), QRectF(self.glass.geometry()))

    def start(self, entrance_snapshot: QPixmap | None = None) -> None:
        if self.disposed:
            return
        self.entering = entrance_snapshot is not None
        self._show_scene(0, defer_clock=self.entering)
        if self.entering:
            self.visual.entrance_prepared = True
            self._entrance_text_opacity = 0.0
            self._entrance_offset = 12
            self.entrance = LearningEntrance(entrance_snapshot, self)
            self.entrance.progress_changed.connect(self._entrance_frame)
            self.entrance.resume_requested.connect(self._resume_entrance)
            self.entrance.show()
            self._layout_overlays()
            self._refresh_glass()
            self.glass.hide()
            self.entrance_animation = QPropertyAnimation(self.entrance, b"progress", self)
            self.entrance_animation.setDuration(LearningEntrance.DURATION_MS)
            self.entrance_animation.setStartValue(0.0)
            self.entrance_animation.setEndValue(1.0)
            self.entrance_animation.finished.connect(self._finish_entrance)
            self.entrance_animation.start()
            if self.paused:
                self.entrance_animation.pause()
        self.setFocus()

    def _entrance_frame(self, value: float) -> None:
        if self.disposed:
            return
        progress = max(0.0, min(1.0, (value * LearningEntrance.DURATION_MS - 500) / 350))
        progress = QEasingCurve(QEasingCurve.Type.OutCubic).valueForProgress(progress)
        self._entrance_offset = round(12 * (1 - progress))
        self._entrance_text_opacity = progress

    def _resume_entrance(self) -> None:
        if self.entering and self.paused:
            self.toggle_pause()

    def _finish_entrance(self) -> None:
        if self.disposed or not self.entering:
            return
        self.entering = False
        self._entrance_offset = 0
        self._entrance_text_opacity = 1.0
        self.glass.show()
        if self.entrance is not None:
            self.entrance.hide()
            self.entrance.deleteLater()
            self.entrance = None
        if self.entrance_animation is not None:
            self.entrance_animation.deleteLater()
            self.entrance_animation = None
        self._layout_overlays()
        self._refresh_glass()
        # The scene's full configured reading time begins only after text is visible.
        if self.animation is not None:
            self.animation.start()
            if self.paused:
                self.animation.pause()

    def _stop_animation(self) -> None:
        if self.animation is not None:
            self.animation.stop()
            self.animation.deleteLater()
            self.animation = None

    def _show_scene(self, index: int, defer_clock: bool = False) -> None:
        if self.disposed:
            return
        self._stop_animation()
        self.index = index
        self.visited.add(index)
        self.summary_visible = False
        scene = self.lesson.scenes[index]
        self.scene_text.setText(scene.text)
        self.glass.setAccessibleName(scene.title + "；" + scene.text)
        self.reading_scroll.verticalScrollBar().setValue(0)
        old = self.visual_host.currentWidget()
        if old is not None:
            self.visual_host.removeWidget(old)
            old.deleteLater()
        self.visual = self.renderers.build(scene, self.content_dir, self.node_name)
        self.visual_host.addWidget(self.visual)
        self.visual_host.setCurrentWidget(self.visual)
        self.animation = QPropertyAnimation(self.visual, b"phase", self)
        self.animation.setDuration(scene.duration_ms)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.valueChanged.connect(self._frame_changed)
        self.animation.finished.connect(self._scene_finished)
        if not defer_clock:
            self.animation.start()
            if self.paused:
                self.animation.pause()
        self._update_pause_text()
        self._layout_overlays()

    def _frame_changed(self, value) -> None:
        self.glass.update()

    def _scene_finished(self) -> None:
        if not self.disposed and not self.paused:
            self.next_scene()

    def activate_text(self) -> None:
        if self.disposed:
            return
        if self.entering:
            self._resume_entrance()
            return
        if self.summary_visible:
            self.request_quiz()
        elif self.paused:
            self.toggle_pause()
        else:
            self.next_scene()

    def next_scene(self) -> None:
        if self.disposed or self.entering or self.summary_visible:
            return
        if self.index + 1 < len(self.lesson.scenes):
            self._show_scene(self.index + 1)
        else:
            self._show_summary()

    def previous_scene(self) -> None:
        if not self.disposed and not self.entering:
            if self.summary_visible:
                self._show_scene(self.index)
            elif self.index > 0:
                self._show_scene(self.index - 1)

    def _show_summary(self) -> None:
        if len(self.visited) != len(self.lesson.scenes):
            return
        self._stop_animation()
        # A quick manual skip must not leave the last picture half faded forever.
        self.visual.set_phase(1.0)
        self.summary_visible = True
        self.scene_text.setText(self.lesson.summary)
        self.glass.setAccessibleName("学习小结；" + self.lesson.summary)
        self.reading_scroll.verticalScrollBar().setValue(0)
        self.glass.set_hint("学习完毕 · 点击此处开始答题")
        self._layout_overlays()

    def request_quiz(self) -> None:
        if not self.disposed and self.summary_visible and len(self.visited) == len(self.lesson.scenes):
            self.quiz_requested.emit()

    def replay(self) -> None:
        if self.disposed or self.entering:
            return
        self.visited.clear()
        self.paused = False
        self._show_scene(0)

    def _update_pause_text(self) -> None:
        if not self.summary_visible:
            self.glass.set_hint("已暂停 · 点击文字框或按空格继续" if self.paused else "")
            self._layout_overlays()

    def pause(self) -> None:
        if self.disposed or self.summary_visible:
            return
        self.paused = True
        if self.entering:
            if self.entrance_animation is not None:
                self.entrance_animation.pause()
            if self.entrance is not None:
                self.entrance.paused = True
                self.entrance.update()
            return
        if self.animation is not None and self.animation.state() == QPropertyAnimation.State.Running:
            self.animation.pause()
        if self.animation is not None and self.lesson.scenes[self.index].transition == "fade":
            # Keep the learning picture readable when focus is lost during its fade.
            if self.animation.currentTime() < 600:
                self.animation.setCurrentTime(600)
        self._update_pause_text()

    def toggle_pause(self) -> None:
        if self.disposed or self.summary_visible:
            return
        if not self.paused:
            self.pause()
            return
        self.paused = False
        if self.entering:
            if self.entrance_animation is not None:
                self.entrance_animation.resume()
            if self.entrance is not None:
                self.entrance.paused = False
                self.entrance.update()
            return
        if self.animation is not None:
            if self.animation.state() == QPropertyAnimation.State.Paused:
                self.animation.resume()
            elif self.animation.currentTime() >= self.animation.duration():
                self.next_scene()
        self._update_pause_text()

    def stop(self) -> None:
        self.disposed = True
        self.entering = False
        if self.entrance_animation is not None:
            self.entrance_animation.stop()
            self.entrance_animation.deleteLater()
            self.entrance_animation = None
        if self.entrance is not None:
            self.entrance.hide()
            self.entrance.deleteLater()
            self.entrance = None
        self._blur_timer.stop()
        self._stop_animation()

    def hideEvent(self, event):
        self.pause()
        super().hideEvent(event)
