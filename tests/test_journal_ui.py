"""Journal presentation must preserve real navigation and learning entry points."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton, QToolButton

from app.content import JsonContentRepository
from app.learning import LearningService
from app.storage import JsonProgressStore
from app.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class JournalUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_style = APP.styleSheet()
        APP.setStyleSheet((ROOT / 'assets/styles/theme.qss').read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        APP.setStyleSheet(cls.old_style)

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
        self.assertTrue(hasattr(window, 'tools'), 'Grouped journal tools are missing')
        return window

    def complete(self, index):
        node = self.pack.nodes[index]
        self.service.complete_lesson(node.id)
        for q in self.service.start_quiz(node.id):
            self.service.submit(node.id, q.id, q.answer)

    def test_grouped_tools_open_pages_and_cancelled_reset_preserves_progress(self):
        self.complete(0)
        window = self.window()
        window.tools.summary_button.click()
        self.assertTrue(any('每一步，都留下收获' in item.text()
                            for item in window.scroll.widget().findChildren(QLabel)))
        window.tools.about_button.click()
        self.assertTrue(any('让每一段学习有据可查' in item.text()
                            for item in window.scroll.widget().findChildren(QLabel)))
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.No):
            window.tools.reset_button.click()
        self.assertTrue(self.service.completed('departure'))
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.tools.reset_button.click()
        self.assertFalse(self.service.completed('departure'))
        self.assertEqual(window.viewed_id, 'departure')

    def test_progress_meter_restores_saved_counts_and_follows_reset(self):
        self.complete(0)
        restored = LearningService(self.pack, JsonProgressStore(self.store.path))
        window = self.window(restored)
        self.assertIn('1 / 8', window.meter.accessibleDescription())
        self.assertIn('10 / 80', window.meter.accessibleDescription())
        window.select_node('departure')
        self.assertIn('1 / 8', window.meter.accessibleDescription())
        with patch.object(QMessageBox, 'question', return_value=QMessageBox.StandardButton.Yes):
            window.tools.reset_button.click()
        self.assertIn('0 / 8', window.meter.accessibleDescription())
        self.assertIn('0 / 80', window.meter.accessibleDescription())

    def test_chapter_page_omits_unused_comparison_and_sources_entries(self):
        window = self.window()
        page = window.scroll.widget()
        actions = [item.text() for item in page.findChildren(QToolButton)]
        self.assertFalse(any('新程对照' in text or '史料出处' in text for text in actions))
        self.assertFalse(any(item.text() == self.pack.nodes[0].modern
                             for item in page.findChildren(QLabel)))

    def test_primary_action_enters_learning_then_resumes_quiz_and_advances(self):
        window = self.window()
        page = window.scroll.widget()
        self.assertTrue(hasattr(page, 'primary_button'), 'Pinned chapter action is missing')
        QTest.mouseClick(page.primary_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(window.player)
        self.assertFalse(self.service.can_quiz('departure'))
        window.player.exit_button.click()
        self.service.complete_lesson('departure')
        window.select_node('departure')
        window.scroll.widget().primary_button.click()
        self.assertIsNone(window.player)
        self.assertEqual(len(self.service.questions_for('departure')), 10)
        self.complete(0)
        window.select_node('departure')
        page = window.scroll.widget()
        page.quiz_button.click()
        self.assertEqual(window.quiz_index, 0)
        self.assertEqual(window.viewed_id, 'departure')
        window.show_panel('detail')
        window.scroll.widget().primary_button.click()
        self.assertEqual(window.viewed_id, 'xiangjiang')

    def test_long_content_scrolls_without_hiding_primary_action_at_minimum_size(self):
        long_node = replace(self.pack.nodes[0], name='扩展章节：很长的标题也应能够完整阅读',
                            event='长篇章节正文。' * 150)
        service = LearningService(replace(self.pack, nodes=(long_node,)), self.store)
        window = self.window(service)
        window.resize(1060, 700)
        APP.processEvents()
        page = window.scroll.widget()
        self.assertTrue(hasattr(page, 'body_scroll'), 'The journal needs a separate reading area')
        APP.processEvents()
        self.assertGreater(page.body_scroll.verticalScrollBar().maximum(), 0)
        page.body_scroll.verticalScrollBar().setValue(page.body_scroll.verticalScrollBar().maximum())
        center = page.primary_button.mapTo(window, page.primary_button.rect().center())
        self.assertIs(window.childAt(center), page.primary_button)
        QTest.mouseClick(page.primary_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(window.player)

    def test_memorial_unlocks_only_after_every_node_is_complete(self):
        self.pack = replace(self.pack, nodes=(self.pack.nodes[0],))
        self.service = LearningService(self.pack, self.store)
        window = self.window()
        window.tools.summary_button.click()
        self.assertFalse(any(item.text() == '献上一束花'
                             for item in window.scroll.widget().findChildren(QPushButton)))
        self.assertIsNone(window.memorial_window)

        self.complete(0)
        window.select_node(self.pack.nodes[0].id)
        window.scroll.widget().primary_button.click()
        QTest.qWait(300)
        self.assertIn('1 / 1', window.meter.accessibleDescription())
        self.assertIsNotNone(window.memorial_window)
        self.assertTrue(window.memorial_window.isWindow())
        self.assertTrue(window.memorial_window.isVisible())
        self.assertGreaterEqual(window.memorial_window.width(), window.width() - 2)
        flower_button = window.memorial_window.flower_button
        flower_button.click()
        people = json.loads((ROOT / 'assets/content/martyrs.json').read_text(encoding='utf-8'))
        self.assertEqual(len(people), 10)
        self.assertEqual(sum(person['gender'] == 'male' for person in people), 5)
        self.assertEqual(sum(person['gender'] == 'female' for person in people), 5)
        shown = next(person for person in people
                     if person['name'] == window.memorial_window.name_label.text())
        self.assertEqual(window.memorial_window.role_label.text(), shown['role'])
        self.assertEqual(window.memorial_window.biography_label.text(), shown['biography'])
        self.assertFalse(window.memorial_window.portrait.pixmap().isNull())
        window.memorial_window.accept()
        self.assertEqual(self.service.summary().completed_nodes, 1)


if __name__ == '__main__':
    unittest.main()
