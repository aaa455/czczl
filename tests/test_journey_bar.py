"""The journey navigation follows saved mastery, independently of the viewed page."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from app.content import JsonContentRepository
from app.learning import LearningService
from app.storage import JsonProgressStore
from app.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class JourneyBarTests(unittest.TestCase):
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
        self.assertTrue(hasattr(window.route_footer, 'station_buttons'),
                        'The footer must expose its accessible station controls')
        return window

    def complete(self, index):
        node = self.service.pack.nodes[index]
        self.service.complete_lesson(node.id)
        for question in self.service.start_quiz(node.id):
            self.service.submit(node.id, question.id, question.answer)

    def test_mouse_and_keyboard_open_locked_and_completed_chapters(self):
        window = self.window()
        stations = window.route_footer.station_buttons
        QTest.mouseClick(stations[3], Qt.MouseButton.LeftButton)
        self.assertEqual(window.viewed_id, 'zunyi')
        self.assertIn('未解锁', stations[3].accessibleDescription())
        self.assertTrue(any('这一站，还在前方' in label.text()
                            for label in window.scroll.widget().findChildren(QLabel)))
        self.complete(0)
        window.refresh()
        stations[0].setFocus()
        QTest.keyClick(stations[0], Qt.Key.Key_Return)
        self.assertEqual(window.viewed_id, 'departure')
        self.assertIn('已完成', stations[0].accessibleDescription())
        stations[1].setFocus()
        QTest.keyClick(stations[1], Qt.Key.Key_Space)
        self.assertEqual(window.viewed_id, 'xiangjiang')

    def test_progress_is_restored_and_review_does_not_move_current_station(self):
        for index in range(3):
            self.complete(index)
        restored = LearningService(self.pack, JsonProgressStore(self.store.path))
        window = self.window(restored)
        stations = window.route_footer.station_buttons
        self.assertEqual([s.state for s in stations],
                         ['completed'] * 3 + ['current'] + ['locked'] * 4)
        self.assertIn('3 / 8', window.route_footer.accessibleDescription())
        window.select_node('departure')
        self.assertEqual(stations[3].state, 'current')
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.confirm_reset()
        self.assertEqual([s.state for s in stations], ['current'] + ['locked'] * 7)

    def test_all_complete_has_no_pending_current_marker(self):
        window = self.window()
        for index in range(8):
            self.complete(index)
        window.refresh()
        self.assertEqual([s.state for s in window.route_footer.station_buttons], ['completed'] * 8)
        self.assertIn('8 / 8', window.route_footer.accessibleDescription())

    def test_stations_remain_clickable_at_supported_sizes_and_hide_for_learning(self):
        window = self.window()
        for width, height in [(1060, 700), (1440, 900)]:
            window.resize(width, height)
            APP.processEvents()
            for station, node in zip(window.route_footer.station_buttons, self.pack.nodes):
                self.assertGreaterEqual(station.width(), 100)
                point = station.mapTo(window, station.rect().center())
                self.assertIs(window.childAt(point), station)
                QTest.mouseClick(station, Qt.MouseButton.LeftButton)
                self.assertEqual(window.viewed_id, node.id)
        window.select_node('departure')
        window.start_learning()
        self.assertFalse(window.route_footer.isVisible())
        window.show_panel('detail')
        APP.processEvents()
        self.assertTrue(window.route_footer.isVisible())

    def test_external_single_chapter_uses_content_label_and_completes(self):
        node = replace(self.pack.nodes[0], id='custom', short_name='自定义章节')
        self.service = LearningService(replace(self.pack, nodes=(node,)), self.store)
        window = self.window()
        stations = window.route_footer.station_buttons
        self.assertEqual(len(stations), 1)
        self.assertEqual(stations[0].text(), '自定义章节')
        self.complete(0)
        window.refresh()
        self.assertEqual(stations[0].state, 'completed')
        QTest.mouseClick(stations[0], Qt.MouseButton.LeftButton)
        self.assertEqual(window.viewed_id, 'custom')

    def test_extended_content_scrolls_keyboard_focus_into_view(self):
        nodes = tuple(replace(self.pack.nodes[i % 8], id=f'external-{i}',
                              short_name=f'扩展章节{i + 1}') for i in range(16))
        self.service = LearningService(replace(self.pack, nodes=nodes), self.store)
        window = self.window()
        window.resize(1060, 700)
        APP.processEvents()
        bar = window.route_footer
        stations = bar.station_buttons
        stations[0].setFocus()
        for station in stations[1:]:
            QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Tab)
            APP.processEvents()
            self.assertIs(APP.focusWidget(), station)
            center = station.mapTo(bar.scroller.viewport(), station.rect().center())
            self.assertTrue(bar.scroller.viewport().rect().contains(center))
        QTest.keyClick(stations[-1], Qt.Key.Key_Return)
        self.assertEqual(window.viewed_id, 'external-15')


if __name__ == '__main__':
    unittest.main()
