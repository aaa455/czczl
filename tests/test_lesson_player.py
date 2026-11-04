"""Behavior tests for actual Qt animations, lifecycle and the learning/quiz handoff."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton

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

    def create(self, lesson=None, entrance=False):
        player = LearningPlayer(lesson or self.lesson, "测试节点", self.directory)
        self.players.append(player)
        player.resize(1060, 600)
        player.show()
        snapshot = QPixmap(1060, 600) if entrance else None
        if snapshot is not None:
            snapshot.fill(QColor("#f3eddf"))
        player.start(snapshot)
        APP.processEvents()
        return player

    def test_manual_progress_back_summary_and_explicit_quiz(self):
        player = self.create()
        requested = QSignalSpy(player.quiz_requested)
        player.request_quiz()
        self.assertEqual(requested.count(), 0)
        QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
        self.assertEqual(player.index, 1)
        QTest.keyClick(player, Qt.Key.Key_Left)
        self.assertEqual(player.index, 0)
        for _ in range(3):
            QTest.keyClick(player, Qt.Key.Key_Right)
        self.assertTrue(player.summary_visible)
        self.assertIsNone(player.animation)
        self.assertEqual(player.visual.get_phase(), 1.0)
        QTest.keyClick(player, Qt.Key.Key_Left)
        self.assertEqual(player.index, 2)
        player.next_scene()
        QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
        self.assertEqual(requested.count(), 1)
        player.replay()
        self.assertEqual(player.index, 0)
        self.assertEqual(player.visited, {0})

    def test_pause_resume_and_stop_prevent_late_callbacks(self):
        player = self.create()
        QTest.qWait(80)
        self.assertGreater(player.animation.currentTime(), 0)
        QTest.keyClick(player, Qt.Key.Key_Space)
        moment = player.animation.currentTime()
        QTest.qWait(80)
        self.assertEqual(player.animation.currentTime(), moment)
        QTest.keyClick(player, Qt.Key.Key_Space)
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
        self.assertTrue(player.summary_visible)
        self.assertEqual(requested.count(), 0)

    def test_hidden_player_pauses_and_text_click_resumes_without_skipping(self):
        player = self.create()
        player.hide()
        self.assertTrue(player.paused)
        self.assertGreaterEqual(player.visual.get_phase() * player.lesson.scenes[0].duration_ms, 600)
        self.assertEqual(player.animation.state(), player.animation.State.Paused)
        player.show()
        APP.processEvents()
        QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
        self.assertFalse(player.paused)
        self.assertEqual(player.index, 0)

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
        self.assertTrue(player.summary_visible)
        player.previous_scene()
        self.assertEqual(player.index, 0)
        self.assertFalse(player.summary_visible)

    def test_only_exit_control_full_window_background_and_bottom_glass_on_resize(self):
        image = QImage(2, 2, QImage.Format.Format_RGB32)
        colors = [QColor("red"), QColor("green"), QColor("blue"), QColor("yellow")]
        for (x, y), color in zip([(0, 0), (1, 0), (0, 1), (1, 1)], colors):
            image.setPixelColor(x, y, color)
        image.save(str(self.directory / "corners.png"))
        scene = replace(self.lesson.scenes[0], image="corners.png", transition="none")
        player = self.create(replace(self.lesson, scenes=(scene,)))
        for width, height in [(1060, 700), (1600, 900)]:
            player.resize(width, height)
            APP.processEvents()
            self.assertEqual(player.visual.size(), player.size())
            rendered = player.visual.grab().toImage()
            points = [(0, 0), (rendered.width() - 1, 0),
                      (0, rendered.height() - 1), (rendered.width() - 1, rendered.height() - 1)]
            for (x, y), color in zip(points, colors):
                self.assertEqual(rendered.pixelColor(x, y), color)
            visible_buttons = [b for b in player.findChildren(QPushButton) if b.isVisible()]
            self.assertEqual(visible_buttons, [player.exit_button])
            self.assertLessEqual(abs(player.glass.geometry().center().x() - player.rect().center().x()), 1)
            self.assertEqual(player.glass.x(), 0)
            self.assertEqual(player.glass.width(), width)
            self.assertGreater(player.glass.y(), height // 2)
            self.assertTrue(player.rect().contains(player.glass.geometry()))
            QTest.qWait(60)
            self.assertFalse(player.glass._backdrop.isNull())
        requested = QSignalSpy(player.back_requested)
        player.exit_button.click()
        self.assertEqual(requested.count(), 1)
        QTest.keyClick(player, Qt.Key.Key_Escape)
        self.assertEqual(requested.count(), 2)

    def test_dragging_text_does_not_advance(self):
        player = self.create()
        QTest.mousePress(player.scene_text, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
        QTest.mouseRelease(player.scene_text, Qt.MouseButton.LeftButton, pos=QPoint(70, 20))
        self.assertEqual(player.index, 0)

    def test_glass_backdrop_tracks_scene_and_bounds_without_a_delayed_old_frame(self):
        scenes = []
        for index, color in enumerate(("red", "blue")):
            image = QImage(600, 400, QImage.Format.Format_RGB32)
            image.fill(QColor(color))
            image.save(str(self.directory / f"{color}.png"))
            scenes.append(replace(self.lesson.scenes[index], image=f"{color}.png"))
        player = self.create(replace(self.lesson, scenes=tuple(scenes)))
        player.animation.pause()
        player.animation.setCurrentTime(1000)
        player._refresh_glass()
        player.next_scene()
        # The next frame must already use the new scene, even before timers fire.
        backdrop = player.glass._backdrop.toImage()
        pixel = backdrop.pixelColor(backdrop.width() // 2, backdrop.height() // 2)
        self.assertGreater(pixel.blue(), pixel.red() + 100)
        self.assertEqual(backdrop.size(), player.glass.size())
        player.pause()
        player.resize(1240, 820)
        self.assertEqual(player.glass._backdrop.size(), player.glass.size())

    def test_glass_crop_uses_logical_coordinates_at_windows_display_scale(self):
        image = QImage(600, 400, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        for y in range(200, 400):
            for x in range(600):
                image.setPixelColor(x, y, QColor("blue"))
        image.save(str(self.directory / "bands.png"))
        scene = replace(self.lesson.scenes[0], image="bands.png", transition="none")
        player = self.create(replace(self.lesson, scenes=(scene,)))
        player._refresh_glass()
        backdrop = player.glass._backdrop.toImage()
        for fraction in (.25, .5, .75):
            pixel = backdrop.pixelColor(round(backdrop.width() * fraction), backdrop.height() // 2)
            self.assertGreater(pixel.alpha(), 100)
            self.assertGreater(pixel.blue(), pixel.red() + 100)

    def test_scene_fade_has_no_glass_brightness_jump_at_600ms(self):
        image = QImage(600, 400, QImage.Format.Format_RGB32)
        image.fill(QColor("white"))
        image.save(str(self.directory / "white.png"))
        scene = replace(self.lesson.scenes[0], image="white.png")
        player = self.create(replace(self.lesson, scenes=(scene,)))
        player.animation.pause()
        player.animation.setCurrentTime(40)
        player._refresh_glass()
        def sample(elapsed):
            player.animation.setCurrentTime(elapsed)
            APP.processEvents()
            QTest.qWait(1)
            image = player.grab().toImage()
            scale = image.devicePixelRatio()
            return image.pixelColor(round(player.width() / 2 * scale),
                                    round((player.glass.y() + 8) * scale))
        before, after = sample(599), sample(601)
        self.assertLessEqual(max(abs(a - b) for a, b in zip(before.getRgb(), after.getRgb())), 3)

    def test_entrance_defers_reading_blocks_skips_and_reveals_text(self):
        player = self.create(entrance=True)
        self.assertTrue(player.entering)
        self.assertEqual(player.animation.state(), player.animation.State.Stopped)
        self.assertEqual(player.animation.currentTime(), 0)
        player.next_scene()
        player.previous_scene()
        player.replay()
        QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
        self.assertEqual(player.index, 0)
        self.assertEqual(player.visited, {0})
        player.entrance_animation.setCurrentTime(600)
        APP.processEvents()
        self.assertGreater(player._entrance_text_opacity, 0)
        self.assertLess(player._entrance_text_opacity, 1)
        self.assertGreater(player._entrance_offset, 0)
        self.assertEqual(player.animation.currentTime(), 0)
        player.resize(1200, 800)
        APP.processEvents()
        self.assertEqual(player.entrance.size(), player.size())
        player.entrance_animation.setCurrentTime(850)
        APP.processEvents()
        self.assertFalse(player.entering)
        self.assertIsNone(player.entrance)
        self.assertEqual(player._entrance_text_opacity, 1)
        self.assertTrue(player.glass.isVisible())
        self.assertEqual(player._entrance_offset, 0)
        self.assertEqual(player.animation.duration(), 12000)
        self.assertEqual(player.animation.state(), player.animation.State.Running)
        self.assertLess(player.animation.currentTime(), 100)

    def test_entrance_pause_resume_and_dispose_cancel_pending_handoff(self):
        player = self.create(entrance=True)
        player.entrance_animation.setCurrentTime(300)
        player.pause()
        QTest.qWait(60)
        self.assertEqual(player.entrance_animation.currentTime(), 300)
        self.assertEqual(player.animation.currentTime(), 0)
        QTest.mouseClick(player.entrance, Qt.MouseButton.LeftButton)
        self.assertFalse(player.paused)
        QTest.qWait(60)
        self.assertGreater(player.entrance_animation.currentTime(), 300)
        exited = QSignalSpy(player.back_requested)
        player.exit_button.click()
        self.assertEqual(exited.count(), 1)
        player.stop()
        player._finish_entrance()
        self.assertIsNone(player.animation)
        self.assertIsNone(player.entrance_animation)
        self.assertIsNone(player.entrance)


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
        self.assertFalse(self.window.header.isVisible())
        self.assertFalse(self.window.statusBar().isVisible())
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        with patch.object(self.window, "isActiveWindow", return_value=False):
            self.window.changeEvent(QEvent(QEvent.Type.ActivationChange))
        self.assertTrue(player.paused)
        player.back_requested.emit()
        self.assertIsNone(self.window.player)
        self.assertTrue(player.disposed)
        self.assertIsNone(player.animation)
        self.assertFalse(player._blur_timer.isActive())
        self.assertTrue(self.window.header.isVisible())
        self.assertTrue(self.window.statusBar().isVisible())
        self.assertFalse(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertFalse(self.service.lesson_learned(self.window.viewed_id))

    def test_complete_save_failure_stays_in_player_then_retry_enters_quiz(self):
        self.window.start_learning()
        player = self.window.player
        if player.paused:
            player.toggle_pause()
        player.entrance_animation.setCurrentTime(850)
        for _ in self.service.lessons[self.window.viewed_id].scenes:
            player.next_scene()
        with patch.object(self.store, "save", side_effect=OSError("read only")), \
                patch.object(QMessageBox, "warning") as warning:
            QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
            warning.assert_called_once()
        self.assertIs(self.window.player, player)
        self.assertFalse(self.service.can_quiz(self.window.viewed_id))
        QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
        self.assertIsNone(self.window.player)
        self.assertTrue(self.service.lesson_learned(self.window.viewed_id))
        self.assertIsNotNone(self.window.answer_widget)
        self.window.start_quiz()
        self.assertIsNone(self.window.player)

    def test_repeated_learning_click_during_entry_keeps_single_player(self):
        before = self.window.geometry()
        self.window.start_learning()
        player = self.window.player
        self.window.start_learning()
        self.assertIs(self.window.player, player)
        self.assertEqual(self.window.geometry(), before)
        player.exit_button.click()
        self.assertIsNone(self.window.player)
        self.assertTrue(player.disposed)
        self.assertIsNone(player.entrance_animation)
        APP.processEvents()
        self.assertEqual(self.window.geometry(), before)

    def test_random_quiz_returns_to_same_round_and_restores_after_restart(self):
        self.service.complete_lesson(self.window.viewed_id)
        self.window.show_panel("quiz")
        questions = self.service.questions_for(self.window.viewed_id)
        self.assertEqual(len(questions), 10)
        question = questions[0]
        self.assertEqual([key for key, _ in self.window.answer_widget.buttons], [o.id for o in question.options])
        for key, choice in self.window.answer_widget.buttons:
            choice.setChecked(key in question.answer)
        self.window.submit_button.click()
        self.window.next_button.click()
        self.window.show_panel("detail")
        self.window.start_quiz()
        self.assertEqual(self.window.quiz_index, 1)
        self.assertEqual(self.service.questions_for(self.window.viewed_id), questions)
        restored = LearningService(self.service.pack, self.store, lessons=self.service.lessons)
        other = MainWindow(restored)
        try:
            other.start_quiz()
            self.assertEqual(other.quiz_index, 1)
            self.assertEqual(restored.questions_for(other.viewed_id), questions)
            self.assertEqual([key for key, _ in other.answer_widget.buttons], [o.id for o in questions[1].options])
        finally:
            other.close()
            other.deleteLater()

    def test_failed_random_round_save_keeps_learning_summary_for_retry(self):
        self.window.start_learning()
        player = self.window.player
        if player.paused:
            player.toggle_pause()
        player.entrance_animation.setCurrentTime(850)
        for _ in player.lesson.scenes:
            player.next_scene()
        self.service.complete_lesson(self.window.viewed_id)
        with patch.object(self.store, "save", side_effect=OSError("read only")), \
                patch.object(QMessageBox, "warning") as warning:
            self.window.start_quiz()
            warning.assert_called_once()
        self.assertIs(self.window.player, player)
        self.assertTrue(player.summary_visible)
        self.assertEqual(self.service.progress.quiz_sessions, {})
        self.window.start_quiz()
        self.assertIsNone(self.window.player)
        self.assertEqual(len(self.service.questions_for(self.window.viewed_id)), 10)


if __name__ == "__main__":
    unittest.main()
