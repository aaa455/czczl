"""Exercise actual Qt buttons through the full route, using isolated test data."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QAbstractAnimation, Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.content import JsonContentRepository
from app.learning import LearningService
from app.lessons import JsonLessonRepository
from app.storage import JsonProgressStore
from app.ui.window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".artifacts/ui")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    # The offscreen Qt platform does not enumerate Windows system fonts.
    # Load installed fonts for screenshots only; do not redistribute OS font files.
    fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    for name in ["msyh.ttc", "simsun.ttc", "georgia.ttf"]:
        if (fonts / name).exists():
            QFontDatabase.addApplicationFont(str(fonts / name))
    app.setFont(QFont("Microsoft YaHei UI", 10))
    app.setStyleSheet((ROOT / "assets/styles/theme.qss").read_text(encoding="utf-8"))
    pack = JsonContentRepository(ROOT / "assets/content").load()
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "progress.json"
        service = LearningService(pack, JsonProgressStore(path),
                                  lessons=JsonLessonRepository(ROOT / "assets/content").load(pack))
        window = MainWindow(service)
        window.show()
        app.processEvents()
        stations = window.route_footer.station_buttons
        assert [s.state for s in stations] == ['current'] + ['locked'] * (len(pack.nodes) - 1)
        assert window.grab().save(str(args.output / "01-route.png"))
        page = window.scroll.widget()
        window.resize(1060, 700)
        app.processEvents()
        action = page.primary_button
        assert window.childAt(action.mapTo(window, action.rect().center())) is action
        assert window.grab().save(str(args.output / "17-journal-small.png"))
        window.resize(1240, 820)
        app.processEvents()
        QTest.mouseClick(stations[-1], Qt.MouseButton.LeftButton)
        assert window.viewed_id == pack.nodes[-1].id
        assert not service.unlocked(pack.nodes[-1].id)
        for index, node in enumerate(pack.nodes):
            QTest.mouseClick(stations[index], Qt.MouseButton.LeftButton)
            assert window.viewed_id == node.id
            window.scroll.widget().primary_button.click()
            player = window.player
            assert player is not None  # The journal action starts learning before the quiz.
            if player.paused:
                player.toggle_pause()
            # Screenshot encoding can outlast the 850ms entrance on CI runners.
            # Freeze its clock while seeking frames, then resume to finish normally.
            entrance = player.entrance_animation
            assert entrance is not None
            entrance.pause()
            if index == 0:
                frames = args.output / "entrance-frames"
                frames.mkdir(exist_ok=True)
                for elapsed in range(0, 850, 50):
                    entrance.setCurrentTime(elapsed)
                    app.processEvents()
                    assert window.grab().save(str(frames / f"{elapsed:04}.png"))
                for elapsed, name in [(0, "11-entry-route"), (180, "12-entry-dim"),
                                      (450, "13-entry-background"), (650, "14-entry-text")]:
                    entrance.setCurrentTime(elapsed)
                    app.processEvents()
                    assert player.animation.currentTime() == 0
                    assert window.grab().save(str(args.output / f"{name}.png"))
            entrance.resume()
            entrance.setCurrentTime(850)
            app.processEvents()
            assert not player.entering
            if index == 0:
                assert window.grab().save(str(frames / "0850.png"))
            if index == 0:
                player.animation.setCurrentTime(1000)
                if player.paused:
                    player.toggle_pause()
                app.processEvents()
                player._refresh_glass()
                assert window.grab().save(str(args.output / "10-learning-playing.png"))
                player.pause()
                app.processEvents()
                player._refresh_glass()
                assert window.grab().save(str(args.output / "06-learning-scene.png"))
                window.resize(1060, 700)
                app.processEvents()
                player._refresh_glass()
                assert window.grab().save(str(args.output / "07-learning-small.png"))
                window.resize(1240, 820)
            for _ in service.lessons[node.id].scenes:
                player.next_scene()
            assert player.summary_visible
            if index == 0:
                app.processEvents()
                player._refresh_glass()
                assert window.grab().save(str(args.output / "08-learning-summary.png"))
            QTest.mouseClick(player.scene_text, Qt.MouseButton.LeftButton)
            assert window.player is None and service.lesson_learned(node.id)
            questions = service.questions_for(node.id)
            assert len(questions) == service.quiz_count(node.id)
            assert len({q.id for q in questions}) == len(questions)
            for qi, question in enumerate(questions):
                app.processEvents()
                if index == 0 and qi == 0:
                    wrong = next(key for key, _ in window.answer_widget.buttons if key not in question.answer)
                    next(b for key, b in window.answer_widget.buttons if key == wrong).click()
                    window.submit_button.click()
                    assert not service.completed(node.id)
                    assert service.summary().first_correct == 0
                for key, choice in window.answer_widget.buttons:
                    choice.setChecked(key in question.answer)
                window.submit_button.click()
                assert service.progress.answers[question.id].mastered
                if index == 0 and qi == 0:
                    app.processEvents()
                    assert window.grab().save(str(args.output / "02-quiz.png"))
                window.next_button.click()
            assert service.completed(node.id)
            assert f'{index + 1} / {len(pack.nodes)}' in window.meter.accessibleDescription()
            assert all(s.state == 'completed' for s in stations[:index + 1])
            if index + 1 < len(stations):
                assert stations[index + 1].state == 'current'
            # Completing the quiz unlocks the next station but waits for explicit departure.
            travel = window.route.travel_animation
            if index < len(pack.nodes) - 1:
                assert travel.state() == QAbstractAnimation.State.Stopped
                window.scroll.widget().primary_button.click()
                assert window.viewed_id == pack.nodes[index + 1].id
                assert travel.state() == QAbstractAnimation.State.Running
                # Capture the real saved-progress animation, including the winding Chishui edge.
                if travel.state() == QAbstractAnimation.State.Running:
                    travel.pause()
                if index in (0, 4):
                    frames = args.output / f"route-frames-{index + 1}"
                    frames.mkdir(exist_ok=True)
                    for elapsed in range(0, travel.duration(), 80):
                        travel.setCurrentTime(elapsed)
                        app.processEvents()
                        assert window.grab().save(str(frames / f"{elapsed:04}.png"))
                travel.resume()
                travel.setCurrentTime(travel.duration())
                assert window.route.arrived_index == index + 1
            assert abs(window.route.travel - min(index + 1, len(pack.nodes) - 1)) < .001
            window.route.arrival_animation.stop()
            app.processEvents()
            assert window.grab().save(str(args.output / f"route-completed-{index + 1}.png"))
        window.show_panel("summary")
        app.processEvents()
        assert window.grab().save(str(args.output / "03-summary.png"))
        summary = service.summary()
        assert summary.completed_nodes == len(pack.nodes)
        assert summary.first_correct == summary.total_questions - 1
        restored = LearningService(pack, JsonProgressStore(path))
        assert restored.summary() == summary
        for node in pack.nodes:
            assert restored.questions_for(node.id) == service.questions_for(node.id)
        window.show_memorial()
        QTest.qWait(800)
        assert window.memorial_window is not None and window.memorial_window.isVisible()
        window.memorial_window.flower_button.click()
        QTest.qWait(950)
        assert window.memorial_window.name_label.text()
        assert not window.memorial_window.portrait.pixmap().isNull()
        assert window.memorial_window.grab().save(str(args.output / "04-memorial.png"))
        window.memorial_window.accept()
        QTest.qWait(350)
        # Minimum window size and completed-node review remain usable.
        window.resize(1060, 700)
        window.select_node(pack.nodes[0].id)
        app.processEvents()
        assert window.grab().save(str(args.output / "05-small-window.png"))
        window.close()
        report = {"ok": True, "nodes": len(pack.nodes), "questions": summary.total_questions,
                  "first_correct": summary.first_correct,
                  "bank_questions": sum(len(n.questions) for n in pack.nodes),
                  "checks": ["locked-node view", "lesson gate and explicit quiz handoff for all nodes",
                             "entrance transition and deferred reading clock", "lesson pause, manual navigation and summary", "wrong-answer retry", "all nodes through UI",
                             "persistent progress and random question/option order", "full-window memorial transition and portrait", "review at minimum size",
                             "landscape background and curved route animation for all chapter completions",
                             "journey bar navigation and saved mastery states for all chapters",
                             "journal primary actions, minimum-size entry and saved progress dial"]}
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
