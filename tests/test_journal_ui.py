"""Journal presentation must preserve real navigation and learning entry points."""
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

    def test_details_expand_current_chapter_content_with_keyboard_access(self):
        window = self.window()
        page = window.scroll.widget()
        self.assertTrue(hasattr(page, 'modern_toggle'), 'Expandable journal content is missing')
        self.assertFalse(page.modern_text.isVisible())
        self.assertFalse(page.sources_text.isVisible())
        QTest.mouseClick(page.modern_toggle, Qt.MouseButton.LeftButton)
        self.assertTrue(page.modern_text.isVisible())
        self.assertEqual(page.modern_text.text(), self.pack.nodes[0].modern)
        page.sources_toggle.setFocus()
        QTest.keyClick(page.sources_toggle, Qt.Key.Key_Space)
        self.assertTrue(page.sources_text.isVisible())
        self.assertIn(self.pack.nodes[0].sources[0], page.sources_text.text())
        self.assertIn('10', page.quiz_note.text())
        APP.processEvents()
        source_center = page.sources_text.mapTo(page.body_scroll.viewport(), page.sources_text.rect().center())
        self.assertTrue(page.body_scroll.viewport().rect().contains(source_center),
                        'Expanded sources must be revealed in the reading viewport')
        page.sources_toggle.click()
        self.assertFalse(page.sources_text.isVisible())

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
                            event='长篇章节正文。' * 150, modern='新程对照长内容。' * 100)
        service = LearningService(replace(self.pack, nodes=(long_node,)), self.store)
        window = self.window(service)
        window.resize(1060, 700)
        APP.processEvents()
        page = window.scroll.widget()
        self.assertTrue(hasattr(page, 'body_scroll'), 'The journal needs a separate reading area')
        page.modern_toggle.click()
        APP.processEvents()
        self.assertGreater(page.body_scroll.verticalScrollBar().maximum(), 0)
        page.body_scroll.verticalScrollBar().setValue(page.body_scroll.verticalScrollBar().maximum())
        center = page.primary_button.mapTo(window, page.primary_button.rect().center())
        self.assertIs(window.childAt(center), page.primary_button)
        QTest.mouseClick(page.primary_button, Qt.MouseButton.LeftButton)
        self.assertIsNotNone(window.player)

    def test_last_chapter_primary_opens_badge_review_for_external_single_chapter(self):
        self.pack = replace(self.pack, nodes=(self.pack.nodes[0],))
        self.service = LearningService(self.pack, self.store)
        self.complete(0)
        window = self.window()
        self.assertIn('1 / 1', window.meter.accessibleDescription())
        window.scroll.widget().primary_button.click()
        self.assertTrue(window.badge_name.isVisible())
        self.assertEqual(self.service.summary().completed_nodes, 1)


if __name__ == '__main__':
    unittest.main()
