"""Composition root. Choose content/store/renderer implementations here."""
import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QStandardPaths, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from app.content import ContentError, JsonContentRepository
from app.learning import LearningService
from app.storage import JsonProgressStore
from app.ui.window import MainWindow


def resource_root() -> Path:
    # PyInstaller sets __file__ relative to the unpacked resource root.
    return Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="足迹长征 Windows桌面程序")
    parser.add_argument("--content-dir", type=Path, help="外部内容目录，内含 nodes.json")
    parser.add_argument("--data-dir", type=Path, help="指定独立存档目录，用于测试或演示")
    parser.add_argument("--smoke-check", type=Path, help="生成界面截图及JSON报告后退出")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ZuJiChangZheng")
    app.setOrganizationName("ZuJiChangZhengTeam")
    app.setFont(QFont("Microsoft YaHei UI", 10))
    stylesheet = resource_root() / "assets" / "styles" / "theme.qss"
    try:
        app.setStyleSheet(stylesheet.read_text(encoding="utf-8"))
        content_dir = args.content_dir or resource_root() / "assets" / "content"
        pack = JsonContentRepository(content_dir).load()
        data_dir = args.data_dir or Path(QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppLocalDataLocation))
        store = JsonProgressStore(data_dir / f"{pack.id}.json")
        service = LearningService(pack, store)
        window = MainWindow(service)
    except (ContentError, ValueError, OSError) as exc:
        if args.smoke_check:
            args.smoke_check.parent.mkdir(parents=True, exist_ok=True)
            args.smoke_check.with_suffix(".error.txt").write_text(str(exc), encoding="utf-8")
        else:
            QMessageBox.critical(None, "无法启动", str(exc))
        return 1
    window.show()
    if args.smoke_check:
        import json
        def capture():
            try:
                args.smoke_check.parent.mkdir(parents=True, exist_ok=True)
                if not window.grab().save(str(args.smoke_check), "PNG"):
                    raise OSError("截图写入失败")
                args.smoke_check.with_suffix(".json").write_text(json.dumps({
                    "ok": True, "nodes": len(pack.nodes),
                    "questions": service.summary().total_questions,
                    "frozen": bool(getattr(sys, "frozen", False)),
                    "content_directory": str(content_dir), "data_directory": str(data_dir),
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                app.exit(0)
            except OSError:
                app.exit(1)
        QTimer.singleShot(500, capture)
    elif store.notice:
        QTimer.singleShot(0, lambda: QMessageBox.information(window, "存档说明", store.notice))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
