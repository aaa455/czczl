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

from PySide6.QtGui import QFont, QFontDatabase, QImage
from PySide6.QtWidgets import QApplication
from app.content import JsonContentRepository
from app.learning import LearningService
from app.lessons import JsonLessonRepository
from app.storage import JsonProgressStore
from app.ui.badge import PngBadgeExporter
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
        assert window.grab().save(str(args.output / "01-route.png"))
        window.select_node(pack.nodes[-1].id)
        assert not service.unlocked(pack.nodes[-1].id)
        for index, node in enumerate(pack.nodes):
            window.select_node(node.id)
            window.start_quiz()
            player = window.player
            assert player is not None  # New learners are directed into the lesson first.
            player.auto.setChecked(False)
            if index == 0:
                player.animation.setCurrentTime(1000)
                player.pause()
                app.processEvents()
                assert window.grab().save(str(args.output / "06-learning-scene.png"))
                window.resize(1060, 700)
                app.processEvents()
                assert window.grab().save(str(args.output / "07-learning-small.png"))
                window.resize(1240, 820)
            for _ in service.lessons[node.id].scenes:
                player.next_button.click()
            assert player.pages.currentIndex() == 1
            if index == 0:
                app.processEvents()
                assert window.grab().save(str(args.output / "08-learning-summary.png"))
            player.quiz_button.click()
            assert window.player is None and service.lesson_learned(node.id)
            for qi, question in enumerate(node.questions):
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
        window.show_panel("summary")
        app.processEvents()
        assert window.grab().save(str(args.output / "03-summary.png"))
        summary = service.summary()
        assert summary.completed_nodes == len(pack.nodes)
        assert summary.first_correct == summary.total_questions - 1
        assert LearningService(pack, JsonProgressStore(path)).summary() == summary
        badge = args.output / "04-badge.png"
        PngBadgeExporter().export(badge, "长征学习者", summary)
        assert QImage(str(badge)).width() == 900
        # Minimum window size and completed-node review remain usable.
        window.resize(1060, 700)
        window.select_node(pack.nodes[0].id)
        app.processEvents()
        assert window.grab().save(str(args.output / "05-small-window.png"))
        window.close()
        report = {"ok": True, "nodes": len(pack.nodes), "questions": summary.total_questions,
                  "first_correct": summary.first_correct,
                  "checks": ["locked-node view", "lesson gate and explicit quiz handoff for all nodes",
                             "lesson pause, manual navigation and summary", "wrong-answer retry", "all nodes through UI",
                             "persistent progress", "badge PNG", "review at minimum size"]}
        (args.output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
