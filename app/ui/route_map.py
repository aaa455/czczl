"""Layered landscape and a saved-progress route, with native Qt path animation."""
import json
from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation,
                            QRectF, Qt, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from app.learning import LearningService


class RouteMap(QWidget):
    node_clicked = Signal(str)
    TRAVEL_MS = 1600

    def __init__(self, service: LearningService, parent=None):
        super().__init__(parent)
        self.service = service
        self.selected = service.current_node().id
        self.setAccessibleName('长征学习路线示意图；也可以使用下方的站点按钮')
        self.setMouseTracking(True)
        assets = Path(__file__).resolve().parents[2] / 'assets'
        layout = json.loads((assets / 'styles/route-map.json').read_text(encoding='utf-8'))
        self._background = QPixmap(str(assets / layout['background']))
        # Other content packs retain their own node positions and chapter order.
        self._illustrated = [n['id'] for n in layout['nodes']] == [n.id for n in service.pack.nodes]
        self._layout = {n['id']: n for n in layout['nodes']} if self._illustrated else {}
        self._edges = layout['edges'] if self._illustrated else None
        self._bottom_inset = 0
        self._top_inset = 0
        self._paths: list[QPainterPath] = []
        self._samples: list[list[QPointF]] = []
        self._geometry_key = None
        self._scaled_background = QPixmap()
        self._paint_map = True
        self._completed = self._completed_count()
        self._reached = service.progress.route_reached_index
        self._travel = float(self._reached)
        self._pulse = 1.0
        self.travel_animation = QPropertyAnimation(self, b'travel', self)
        self.travel_animation.setDuration(self.TRAVEL_MS)
        self.travel_animation.setEasingCurve(QEasingCurve.Type.Linear)
        self.travel_animation.finished.connect(self._arrive)
        self.arrival_animation = QVariantAnimation(self)
        self.arrival_animation.setDuration(850)
        self.arrival_animation.setStartValue(0.0)
        self.arrival_animation.setEndValue(1.0)
        self.arrival_animation.valueChanged.connect(self._set_pulse)

    def _completed_count(self) -> int:
        count = 0
        for node in self.service.pack.nodes:
            if not self.service.completed(node.id):
                break
            count += 1
        return count

    def _get_travel(self) -> float:
        return self._travel

    def _set_travel(self, value: float) -> None:
        self._travel = float(value)
        self.update()

    travel = Property(float, _get_travel, _set_travel)

    @property
    def arrived_index(self) -> int:
        return min(int(self._travel + 1e-8), len(self.service.pack.nodes) - 1)

    def _set_pulse(self, value: float) -> None:
        self._pulse = float(value)
        self.update()

    def _arrive(self) -> None:
        if not self._paint_map:
            return
        self.arrival_animation.stop()
        self.arrival_animation.start()

    def sync_progress(self) -> None:
        completed = self._completed_count()
        final_completion = completed > self._completed and completed == len(self.service.pack.nodes)
        self._completed = completed
        reached = self.service.progress.route_reached_index
        if reached == self._reached:
            if final_completion and reached == len(self.service.pack.nodes) - 1:
                self._arrive()
            self.update()
            return
        previous = self._reached
        self._reached = reached
        target = float(reached)
        self.travel_animation.stop()
        self.arrival_animation.stop()
        self._pulse = 1.0
        if reached < previous or not self._paint_map:
            self.travel = target
        elif self._travel < target:
            self.travel_animation.setStartValue(self._travel)
            self.travel_animation.setEndValue(target)
            self.travel_animation.start()
        else:
            # The final chapter has no outgoing edge; celebrate its own node.
            self._arrive()

    def stop_animations(self) -> None:
        self.travel_animation.stop()
        self.arrival_animation.stop()
        self._pulse = 1.0
        self.travel = float(self._reached)

    def set_map_visible(self, visible: bool) -> None:
        if not visible:
            self.stop_animations()
        self._paint_map = visible
        self.update()

    def set_bottom_inset(self, height: int) -> None:
        height = max(0, height)
        if height != self._bottom_inset:
            self._bottom_inset = height
            self.update()

    def set_top_inset(self, height: int) -> None:
        height = max(0, height)
        if height != self._top_inset:
            self._top_inset = height
            self.update()

    def art_rect(self) -> QRectF:
        return QRectF(0, self._top_inset, self.width(),
                      max(1, self.height() - self._top_inset - self._bottom_inset))

    def point(self, position: tuple[float, float]) -> QPointF:
        rect = self.art_rect()
        return QPointF(rect.left() + position[0] * rect.width(),
                       rect.top() + position[1] * rect.height())

    def node_point(self, node_id: str) -> QPointF:
        node = self.service.node(node_id)
        position = self._layout[node_id]['position'] if node_id in self._layout else node.position
        return self.point(position)

    def _ensure_geometry(self) -> None:
        key = (self.width(), self.height(), self._top_inset, self._bottom_inset)
        if key == self._geometry_key:
            return
        self._geometry_key = key
        self._paths, self._samples = [], []
        nodes = self.service.pack.nodes
        for index in range(len(nodes) - 1):
            path = QPainterPath(self.node_point(nodes[index].id))
            if self._edges is not None:
                for curve in self._edges[index]:
                    path.cubicTo(self.point(curve[1]), self.point(curve[2]), self.point(curve[3]))
            else:
                path.lineTo(self.node_point(nodes[index + 1].id))
            length = path.length()
            samples = [path.pointAtPercent(path.percentAtLength(length * i / 160)) for i in range(161)]
            self._paths.append(path)
            self._samples.append(samples)
        self._scaled_background = self._background.scaled(
            self.art_rect().size().toSize(), Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

    def _edge_point(self, index: int, fraction: float) -> QPointF:
        samples = self._samples[index]
        position = max(0.0, min(1.0, fraction)) * (len(samples) - 1)
        offset = min(int(position), len(samples) - 2)
        return samples[offset] + (samples[offset + 1] - samples[offset]) * (position - offset)

    def travel_point(self) -> QPointF:
        self._ensure_geometry()
        if not self._paths:
            return self.node_point(self.service.pack.nodes[0].id)
        index = min(int(self._travel), len(self._paths) - 1)
        return self._edge_point(index, self._travel - index)

    def _partial_path(self, index: int, fraction: float) -> QPainterPath:
        samples = self._samples[index]
        path = QPainterPath(samples[0])
        for point in samples[1:int(fraction * (len(samples) - 1)) + 1]:
            path.lineTo(point)
        path.lineTo(self._edge_point(index, fraction))
        return path

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#f1dfbf'))
        if not self._paint_map:
            return
        self._ensure_geometry()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, self._top_inset, self._scaled_background)
        scale = max(0.65, self.width() / 2048)
        # Future route is muted; the completed path is saturated red.
        painter.setPen(QPen(QColor(153, 82, 61, 108), 2.6 * scale,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for path in self._paths:
            painter.drawPath(path)
        painter.setPen(QPen(QColor('#a43c2e'), 4.5 * scale,
                            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        for index, path in enumerate(self._paths):
            fraction = max(0.0, min(1.0, self._travel - index))
            if fraction >= 1:
                painter.drawPath(path)
            elif fraction > 0:
                painter.drawPath(self._partial_path(index, fraction))
        if self.travel_animation.state() != QPropertyAnimation.State.Stopped:
            tip = self.travel_point()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(255, 234, 176, 125))
            painter.drawEllipse(tip, 13 * scale, 13 * scale)
            painter.setBrush(QColor('#ae402c'))
            painter.drawEllipse(tip, 5 * scale, 5 * scale)
        font = QFont('Microsoft YaHei UI')
        font.setPixelSize(max(12, round(25 * scale)))
        painter.setFont(font)
        for index, node in enumerate(self.service.pack.nodes):
            point = self.node_point(node.id)
            reached = index <= self.arrived_index
            done = self.service.completed(node.id)
            if self.selected == node.id:
                painter.setPen(QPen(QColor('#b58d47'), 1.6))
                painter.setBrush(QColor(248, 225, 175, 90))
                painter.drawEllipse(point, 16 * scale, 16 * scale)
            if index == self.arrived_index and self._pulse < 1:
                radius = (14 + 19 * self._pulse) * scale
                painter.setPen(QPen(QColor(167, 62, 42, round(190 * (1-self._pulse))), 2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(point, radius, radius)
            painter.setPen(QPen(QColor('#9e3a2c' if reached else '#b69a7b'), 1.6))
            painter.setBrush(QColor('#f4dfb8'))
            radius = 9 * scale
            painter.drawEllipse(point, radius, radius)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#9e3a2c' if done or reached else '#bd9d78'))
            painter.drawEllipse(point, radius * .53, radius * .53)
            self._draw_label(painter, node, point, scale, reached)
        painter.end()

    def _draw_label(self, painter, node, point, scale, reached):
        spec = self._layout.get(node.id, {})
        dx, dy = spec.get('label_offset', (22, -10))
        x, y = point.x() + dx * scale, point.y() + dy * scale
        width = painter.fontMetrics().horizontalAdvance(node.short_name)
        anchor = spec.get('label_anchor', 'left')
        if anchor == 'right':
            x -= width
        elif anchor == 'center':
            x -= width / 2
        x = max(8, min(x, self.width() - width - 8))
        baseline = max(18, min(y + painter.fontMetrics().ascent(), self.art_rect().bottom() - 8))
        text = QPainterPath()
        text.addText(QPointF(x, baseline), painter.font(), node.short_name)
        # Paint the halo first so it cannot swallow small Chinese glyph strokes.
        halo = QPen(QColor(247, 224, 184, 235), 3,
                    Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(text, halo)
        painter.fillPath(text, QColor('#6e3226' if reached else '#876b53'))

    def mousePressEvent(self, event):
        if self._paint_map and event.button() == Qt.MouseButton.LeftButton:
            for node in self.service.pack.nodes:
                if (event.position() - self.node_point(node.id)).manhattanLength() <= 24:
                    self.node_clicked.emit(node.id)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        active = self._paint_map and any(
            (event.position() - self.node_point(n.id)).manhattanLength() <= 24
            for n in self.service.pack.nodes)
        self.setCursor(Qt.CursorShape.PointingHandCursor if active else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
