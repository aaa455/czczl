"""Route progress is driven by saved mastery, not by repaint or page changes."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.content import JsonContentRepository
from app.learning import LearningService
from app.storage import JsonProgressStore
from app.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class RouteMapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pack = JsonContentRepository(ROOT / 'assets/content').load()
        self.store = JsonProgressStore(Path(self.tmp.name) / 'progress.json')
        self.service = LearningService(self.pack, self.store)
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        APP.processEvents()

    def window(self, service=None):
        window = MainWindow(service or self.service)
        self.windows.append(window)
        window.show()
        APP.processEvents()
        return window

    def complete(self, index):
        node = self.pack.nodes[index]
        self.service.complete_lesson(node.id)
        for question in self.service.start_quiz(node.id):
            self.service.submit(node.id, question.id, question.answer)

    def test_last_correct_answer_starts_route_once_and_refresh_does_not_rewind(self):
        window = self.window()
        node = self.pack.nodes[0]
        self.service.complete_lesson(node.id)
        questions = self.service.start_quiz(node.id)
        for question in questions[:-1]:
            self.service.submit(node.id, question.id, question.answer)
        window.quiz_index = len(questions) - 1
        window.show_panel('quiz')
        for key, choice in window.answer_widget.buttons:
            choice.setChecked(key in questions[-1].answer)
        self.assertTrue(hasattr(window.route, 'travel_animation'), 'Route completion animation is missing')
        window.submit_answer()
        animation = window.route.travel_animation
        self.assertEqual(animation.state(), QAbstractAnimation.State.Running)
        self.assertEqual(window.route.arrived_index, 0)
        animation.pause()
        animation.setCurrentTime(animation.duration() // 2)
        halfway = window.route.travel
        self.assertGreater(halfway, 0)
        self.assertLess(halfway, 1)
        for _ in range(3):
            window.refresh()
        self.assertEqual(window.route.travel, halfway)
        animation.resume()
        animation.setCurrentTime(animation.duration())
        self.assertAlmostEqual(window.route.travel, 1)
        self.assertEqual(window.route.arrived_index, 1)
        window.select_node(node.id)
        self.assertEqual(animation.state(), QAbstractAnimation.State.Stopped)

    def test_saved_completion_restores_route_without_replaying_and_reset_cancels_animation(self):
        self.complete(0)
        restored = LearningService(self.pack, JsonProgressStore(self.store.path))
        window = self.window(restored)
        self.assertTrue(hasattr(window.route, 'travel_animation'), 'Saved route restoration is missing')
        self.assertAlmostEqual(window.route.travel, 1)
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Stopped)
        self.service.complete_lesson(self.pack.nodes[1].id)
        for question in self.service.start_quiz(self.pack.nodes[1].id):
            self.service.submit(self.pack.nodes[1].id, question.id, question.answer)
        window.service = self.service
        window.route.service = self.service
        window.refresh()
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Running)
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.confirm_reset()
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Stopped)
        self.assertEqual(window.route.travel, 0)
        self.assertEqual(window.route.arrived_index, 0)
        QTest.qWait(30)
        self.assertEqual(window.route.travel, 0)

    def test_clickable_nodes_share_background_coordinates_after_resize(self):
        window = self.window()
        self.assertIs(window.centralWidget(), window.route, 'Landscape must fill the main window')
        for width, height in [(1060, 700), (1440, 900)]:
            window.resize(width, height)
            APP.processEvents()
            for node in self.pack.nodes:
                point = window.route.node_point(node.id).toPoint()
                target = window.route.childAt(point) or window.route
                local = target.mapFrom(window.route, point)
                QTest.mouseClick(target, Qt.MouseButton.LeftButton, pos=local)
                self.assertEqual(window.viewed_id, node.id, f'Node hit target lost at {width}x{height}: {node.id}')

    def test_curve_tip_moves_by_arc_length_and_ends_at_next_node(self):
        window = self.window()
        self.assertTrue(hasattr(window.route, 'travel_animation'), 'Curved route animation is missing')
        self.complete(0)
        window.refresh()
        animation = window.route.travel_animation
        animation.pause()
        points = []
        for elapsed in [0, 400, 800, 1200, 1600]:
            animation.setCurrentTime(elapsed)
            points.append(window.route.travel_point())
        self.assertLess((points[0] - window.route.node_point(self.pack.nodes[0].id)).manhattanLength(), 1)
        self.assertLess((points[-1] - window.route.node_point(self.pack.nodes[1].id)).manhattanLength(), 1)
        distances = [(b-a).manhattanLength() for a,b in zip(points, points[1:])]
        self.assertGreater(min(distances), 0)
        self.assertLess(max(distances) / min(distances), 2)

    def test_final_chapter_pulses_final_node_without_extra_segment(self):
        for index in range(7):
            self.complete(index)
        window = self.window()
        self.assertTrue(hasattr(window.route, 'arrival_animation'), 'Arrival pulse is missing')
        self.complete(7)
        window.refresh()
        self.assertEqual(window.route.travel, 7)
        self.assertEqual(window.route.arrived_index, 7)
        self.assertEqual(window.route.arrival_animation.state(), QAbstractAnimation.State.Running)
        window.close()
        self.assertEqual(window.route.arrival_animation.state(), QAbstractAnimation.State.Stopped)

    def test_wrong_answer_and_failed_save_do_not_advance_the_route(self):
        window = self.window()
        node = self.pack.nodes[0]
        self.service.complete_lesson(node.id)
        questions = self.service.start_quiz(node.id)
        for question in questions[:-1]:
            self.service.submit(node.id, question.id, question.answer)
        window.quiz_index = len(questions) - 1
        window.show_panel('quiz')
        wrong = next(key for key, _ in window.answer_widget.buttons if key not in questions[-1].answer)
        for key, choice in window.answer_widget.buttons:
            choice.setChecked(key == wrong)
        window.submit_answer()
        self.assertEqual(window.route.travel, 0)
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Stopped)
        for key, choice in window.answer_widget.buttons:
            choice.setChecked(key in questions[-1].answer)
        with patch.object(self.store, 'save', side_effect=OSError('disk full')), \
                patch.object(QMessageBox, 'warning'):
            window.submit_answer()
        self.assertFalse(self.service.completed(node.id))
        self.assertEqual(window.route.travel, 0)
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Stopped)

    def test_resize_and_entering_lesson_preserve_route_progress(self):
        window = self.window()
        self.complete(0)
        window.refresh()
        animation = window.route.travel_animation
        animation.pause()
        animation.setCurrentTime(800)
        phase = window.route.travel
        window.resize(1440, 900)
        APP.processEvents()
        self.assertAlmostEqual(window.route.travel, phase)
        animation.resume()
        animation.setCurrentTime(animation.duration())
        window.select_node(self.pack.nodes[1].id)
        window.start_learning()
        self.assertEqual(window.route.travel, 1)
        self.assertEqual(window.route.arrival_animation.state(), QAbstractAnimation.State.Stopped)
        window.show_panel('detail')
        self.assertEqual(window.route.travel, 1)
        self.assertEqual(window.route.travel_animation.state(), QAbstractAnimation.State.Stopped)


if __name__ == '__main__':
    unittest.main()
