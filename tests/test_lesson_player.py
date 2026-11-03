"""Behavior tests for actual Qt animations, lifecycle and the learning/quiz handoff."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QMessageBox

from app.content import JsonContentRepository
from app.learning import LearningService
from app.lessons import JsonLessonRepository
from app.models import LearningScene, Lesson
from app.storage import JsonProgressStore
from app.ui.lesson_player import LearningPlayer, SceneRendererRegistry, ImageTextVisual
from app.ui.window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
APP = QApplication.instance() or QApplication([])


class PlayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.lesson = Lesson("node", tuple(LearningScene(str(i), f"标题{i}", "学习占位正文",
                                                          duration_ms=12000) for i in range(3)), "小结")
        self.players = []

    def tearDown(self):
        for player in self.players:
            player.stop()
            player.close()
            player.deleteLater()
        APP.processEvents()

    def create(self, lesson=None):
        player = LearningPlayer(lesson or self.lesson, "测试节点", self.directory)
        self.players.append(player)
        player.resize(1060, 600)
        player.show()
        player.start()
        APP.processEvents()
        return player

    def test_manual_progress_back_summary_and_explicit_quiz(self):
        player = self.create()
        requested = QSignalSpy(player.quiz_requested)
        player.request_quiz()
        self.assertEqual(requested.count(), 0)
        self.assertFalse(player.previous_button.isEnabled())
        player.next_button.click()
        self.assertEqual(player.index, 1)
        player.previous_button.click()
        self.assertEqual(player.index, 0)
        for _ in range(3):
            player.next_button.click()
        self.assertEqual(player.pages.currentIndex(), 1)
        self.assertIsNone(player.animation)
        player.previous_button.click()
        self.assertEqual(player.index, 2)
        player.next_button.click()
        player.quiz_button.click()
        self.assertEqual(requested.count(), 1)
        player.replay()
        self.assertEqual(player.index, 0)
        self.assertEqual(player.visited, {0})

    def test_pause_resume_and_stop_prevent_late_callbacks(self):
        player = self.create()
        QTest.qWait(80)
        self.assertGreater(player.animation.currentTime(), 0)
        player.pause_button.click()
        moment = player.animation.currentTime()
        QTest.qWait(80)
        self.assertEqual(player.animation.currentTime(), moment)
        player.pause_button.click()
        QTest.qWait(80)
        self.assertGreater(player.animation.currentTime(), moment)
        player.stop()
        index = player.index
        QTest.qWait(80)
        player._scene_finished()
        self.assertEqual(player.index, index)
        self.assertIsNone(player.animation)

    def test_auto_play_advances_but_never_starts_quiz_itself(self):
        player = self.create()
        requested = QSignalSpy(player.quiz_requested)
        for i in range(3):
            # Drive the real animation clock to its end without waiting 36 seconds.
            self.assertEqual(player.index, i)
            player.animation.setCurrentTime(player.animation.duration())
            APP.processEvents()
        self.assertEqual(player.pages.currentIndex(), 1)
        self.assertEqual(requested.count(), 0)

    def test_manual_mode_holds_and_hidden_player_pauses(self):
        player = self.create()
        player.auto.setChecked(False)
        player.animation.setCurrentTime(player.animation.duration())
        self.assertEqual(player.index, 0)
        player.next_button.click()
        player.hide()
        self.assertTrue(player.paused)
        self.assertEqual(player.animation.state(), player.animation.State.Paused)

    def test_image_replacement_missing_image_fallback_and_long_text(self):
        image = QImage(600, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("#b99676"))
        self.assertTrue(image.save(str(self.directory / "test.png")))
        real = replace(self.lesson.scenes[0], image="test.png", text="学习文字。" * 500)
        missing = replace(real, id="missing", image="missing.png")
        player = self.create(replace(self.lesson, scenes=(real, missing)))
        self.assertFalse(player.visual.pixmap.isNull())
        APP.processEvents()
        self.assertGreater(player.reading_scroll.verticalScrollBar().maximum(), 0)
        player.next_scene()
        self.assertTrue(player.visual.pixmap.isNull())
        self.assertIn("不可用", player.visual.image_state)
        self.assertEqual(player.scene_text.text(), missing.text)

    def test_single_scene_summary_can_return_and_renderer_extension(self):
        registry = SceneRendererRegistry()
        registry.register("custom", ImageTextVisual)
        scene = replace(self.lesson.scenes[0], kind="custom")
        player = LearningPlayer(replace(self.lesson, scenes=(scene,)), "扩展", self.directory, registry)
        self.players.append(player)
        player.start()
        player.next_scene()
        self.assertEqual(player.pages.currentIndex(), 1)
        player.previous_scene()
        self.assertEqual(player.index, 0)
        self.assertEqual(player.pages.currentIndex(), 0)


class WindowHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        pack = JsonContentRepository(ROOT / "assets/content").load()
        self.store = JsonProgressStore(Path(self.tmp.name) / "progress.json")
        self.service = LearningService(pack, self.store,
            lessons=JsonLessonRepository(ROOT / "assets/content").load(pack))
        self.window = MainWindow(self.service)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        APP.processEvents()

    def test_quiz_gate_switch_cleanup_and_deactivation(self):
        self.window.start_quiz()
        player = self.window.player
        self.assertIsNotNone(player)
        with patch.object(self.window, "isActiveWindow", return_value=False):
            self.window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertTrue(player.paused)
        player.back_requested.emit()
        self.assertIsNone(self.window.player)
        self.assertTrue(player.disposed)
        self.assertIsNone(player.animation)
        self.assertFalse(self.service.lesson_learned(self.window.viewed_id))

    def test_complete_save_failure_stays_in_player_then_retry_enters_quiz(self):
        self.window.start_learning()
        player = self.window.player
        for _ in self.service.lessons[self.window.viewed_id].scenes:
            player.next_scene()
        with patch.object(self.store, "save", side_effect=OSError("read only")), \
                patch.object(QMessageBox, "warning") as warning:
            player.quiz_button.click()
            warning.assert_called_once()
        self.assertIs(self.window.player, player)
        self.assertFalse(self.service.can_quiz(self.window.viewed_id))
        player.quiz_button.click()
        self.assertIsNone(self.window.player)
        self.assertTrue(self.service.lesson_learned(self.window.viewed_id))
        self.assertIsNotNone(self.window.answer_widget)
        self.window.start_quiz()
        self.assertIsNone(self.window.player)


if __name__ == "__main__":
    unittest.main()
