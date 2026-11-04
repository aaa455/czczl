"""Native shell and replaceable right-hand panels."""
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
    QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from app.learning import LearningService
from app.ui.questions import QuestionViewRegistry, default_views
from app.ui.route_map import RouteMap
from app.ui.journey_bar import JourneyBar
from app.ui.journal_header import JournalProgress, JournalTools
from app.ui.journal_page import ChapterPage, PaperPanel
from app.ui.lesson_player import LearningPlayer, SceneRendererRegistry, default_scene_renderers
from app.ui.memorial import MemorialWindow


def label(text: str, role: str = "body") -> QLabel:
    widget = QLabel(text)
    widget.setObjectName(role)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    return widget


def button(text: str, callback: Callable, secondary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setProperty("secondary", secondary)
    widget.setMinimumHeight(40)
    widget.clicked.connect(lambda checked=False: callback())
    return widget


class MainWindow(QMainWindow):
    def __init__(self, service: LearningService,
                 question_views: QuestionViewRegistry | None = None,
                 content_dir: Path | None = None,
                 scene_renderers: SceneRendererRegistry | None = None,
                 music_path: Path | None = None):
        super().__init__()
        self.service = service
        self.question_views = question_views or default_views()
        self.content_dir = content_dir or Path(__file__).resolve().parents[2] / "assets/content"
        self.assets_dir = Path(__file__).resolve().parents[2] / "assets"
        self.scene_renderers = scene_renderers or default_scene_renderers()
        self.player: LearningPlayer | None = None
        self.memorial_window: MemorialWindow | None = None
        self._route_opacity: QGraphicsOpacityEffect | None = None
        self._route_transition: QPropertyAnimation | None = None
        self.music_player = None
        self.music_output = None
        self.music_enabled = music_path is not None
        if music_path is not None:
            if not music_path.is_file():
                raise OSError(f"背景音乐文件不存在：{music_path}")
            self.music_output = QAudioOutput(self)
            self.music_output.setVolume(0.25)
            self.music_player = QMediaPlayer(self)
            self.music_player.setAudioOutput(self.music_output)
            self.music_player.setSource(QUrl.fromLocalFile(str(music_path)))
            self.music_player.setLoops(QMediaPlayer.Loops.Infinite)
            self.music_player.errorOccurred.connect(self._music_failed)
        for node in service.pack.nodes:
            for scene in service.lessons[node.id].scenes:
                if not self.scene_renderers.supports(scene.kind):
                    raise ValueError(f"分镜缺少渲染器：{scene.kind}")
            for question in node.questions:
                if not self.question_views.supports(question.kind):
                    raise ValueError(f"题型缺少界面：{question.kind}")
        self.viewed_id = service.current_node().id
        self.quiz_index = 0
        self._panels: dict[str, Callable[[], QWidget]] = {}
        self.setWindowTitle("足迹长征 · 路线交互与知识闯关")
        self.resize(1240, 820)
        self.setMinimumSize(1060, 700)
        root = RouteMap(service)
        self.route = root
        self.route.node_clicked.connect(self.select_node)
        root.setObjectName("landscapeRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        header = QFrame()
        self.header = header
        header.setObjectName("header")
        header.setFixedHeight(87)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(25, 18, 25, 18)
        seal = label("长", "seal")
        seal.setAlignment(Qt.AlignmentFlag.AlignCenter)
        seal.setFixedSize(48, 48)
        header_layout.addWidget(seal)
        brand = QVBoxLayout()
        brand.addWidget(label(service.pack.title, "brand"))
        brand.addWidget(label("路线交互 · 知识闯关", "subtitle"))
        header_layout.addLayout(brand)
        header_layout.addStretch()
        self.meter = JournalProgress()
        header_layout.addWidget(self.meter)
        header_layout.addSpacing(15)
        self.tools = JournalTools(has_music=self.music_player is not None)
        if self.tools.music_button is not None:
            self.tools.music_button.clicked.connect(self.toggle_music)
        self.tools.summary_button.clicked.connect(lambda: self.show_panel("summary"))
        self.tools.about_button.clicked.connect(lambda: self.show_panel("about"))
        self.tools.reset_button.clicked.connect(self.confirm_reset)
        header_layout.addWidget(self.tools)
        root_layout.addWidget(header)
        workspace = QWidget()
        workspace.setObjectName("routeWorkspace")
        workspace.setMouseTracking(True)
        workspace_layout = QHBoxLayout(workspace)
        workspace_layout.setContentsMargins(26, 12, 24, 0)
        workspace_layout.setSpacing(24)
        left = QWidget()
        left.setMouseTracking(True)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        for text, role in [("THE LONG MARCH · 学习之旅", "eyebrow"),
                           ("循着足迹，走进历史", "hero"),
                           ("阅读一段历史，完成一次思考，点亮下一站。", "muted")]:
            heading = label(text, role)
            heading.setMaximumWidth(380)
            left_layout.addWidget(heading)
        left_layout.addStretch()
        workspace_layout.addWidget(left, 1)
        footer = JourneyBar(service)
        self.route_footer = footer
        footer.node_clicked.connect(self.select_node)
        panel = PaperPanel()
        self.route_panel = panel
        panel.setObjectName("journalPaper")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(6, PaperPanel.TOP_GAP + 1, 12, 11)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_layout.addWidget(self.scroll)
        workspace_layout.addWidget(panel, 0, Qt.AlignmentFlag.AlignTop)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(workspace)
        root_layout.addWidget(self.content_stack, 1)
        root_layout.addWidget(footer)
        self.setCentralWidget(root)
        for name, factory in [("detail", self.detail_panel), ("quiz", self.quiz_panel),
                              ("summary", self.summary_panel), ("locked", self.locked_panel),
                              ("about", self.about_panel)]:
            self.register_panel(name, factory)
        self.statusBar().showMessage(
            "内容预览版 · 史料及题目待团队核验" if service.pack.review_status == "draft"
            else "进度自动保存在本机 · 核心功能可离线使用")
        self.refresh()
        self.show_panel("detail")
        QTimer.singleShot(0, self._layout_route_overlay)
        if self.music_player is not None:
            self.music_player.play()

    def toggle_music(self) -> None:
        if self.music_player is None:
            return
        self.music_enabled = not self.music_enabled
        if self.music_enabled:
            self.music_player.play()
        else:
            self.music_player.pause()
        self.tools.music_button.setText("音乐：开" if self.music_enabled else "音乐：关")
        self.tools.music_button.setAccessibleName("关闭背景音乐" if self.music_enabled else "播放背景音乐")
        if self.player is not None:
            self.player.set_music_enabled(self.music_enabled)

    def _music_failed(self, error, description: str) -> None:
        if error == QMediaPlayer.Error.NoError:
            return
        self.music_enabled = False
        if self.tools.music_button is not None:
            self.tools.music_button.setText("音乐不可用")
            self.tools.music_button.setToolTip(description)
            self.tools.music_button.setEnabled(False)
        if self.player is not None and self.player.music_button is not None:
            self.player.music_button.setText("音乐不可用")
            self.player.music_button.setToolTip(description)
            self.player.music_button.setEnabled(False)

    def _layout_route_overlay(self) -> None:
        self.route.layout().activate()
        self.route.set_bottom_inset(self.route_footer.height())
        self.route.set_top_inset(self.header.height())
        self.route_panel.setFixedWidth(max(378, min(430, round(self.route.width() * .331))))
        # Keep the lower-right start and the red progress line visible below the card.
        height = round(self.route.art_rect().height() * .73)
        self.route_panel.setFixedHeight(max(286, min(430, height)) + PaperPanel.TOP_GAP)
        self.content_stack.widget(0).layout().activate()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'route_panel'):
            QTimer.singleShot(0, self._layout_route_overlay)

    def register_panel(self, name: str, factory: Callable[[], QWidget]) -> None:
        if name in self._panels:
            raise ValueError(f"面板重复注册：{name}")
        self._panels[name] = factory

    def show_panel(self, name: str) -> None:
        if name == "quiz" and not self.service.can_quiz(self.viewed_id):
            self.start_learning()
            return
        if name == "quiz" and not self.service.questions_for(self.viewed_id):
            self.start_quiz()
            return
        self._leave_learning()
        widget = self._panels[name]()
        old = self.scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        self.scroll.setWidget(widget)
        self.scroll.verticalScrollBar().setValue(0)

    def new_panel(self, eyebrow: str, title: str, meta: str = ""):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 20)
        layout.setSpacing(13)
        layout.addWidget(label(eyebrow, "eyebrow"))
        layout.addWidget(label(title, "title"))
        if meta:
            layout.addWidget(label(meta, "muted"))
        return widget, layout

    def refresh(self) -> None:
        summary = self.service.summary()
        self.meter.refresh(summary)
        self.route_footer.refresh(self.service)
        self.route.selected = self.viewed_id
        self.route.sync_progress()

    def select_node(self, node_id: str) -> None:
        self.viewed_id = node_id
        self.refresh()
        self.show_panel("detail" if self.service.unlocked(node_id) else "locked")

    def detail_panel(self) -> QWidget:
        node = self.service.node(self.viewed_id)
        index = self.service.pack.nodes.index(node)
        page = ChapterPage(node, index, len(self.service.pack.nodes),
                           learned=self.service.lesson_learned(node.id),
                           completed=self.service.completed(node.id),
                           can_quiz=self.service.can_quiz(node.id))
        page.learn_requested.connect(self.start_learning)
        page.quiz_requested.connect(self.start_quiz)
        if index < len(self.service.pack.nodes) - 1:
            next_id = self.service.pack.nodes[index + 1].id
            page.advance_requested.connect(lambda: self.advance_to_next(node.id, next_id))
        else:
            page.advance_requested.connect(self.show_memorial)
        return page

    def advance_to_next(self, node_id: str, next_id: str) -> None:
        try:
            self.service.depart(node_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法出发", str(exc))
            return
        self.route.sync_progress()
        self.select_node(next_id)

    def locked_panel(self) -> QWidget:
        widget, layout = self.new_panel("尚未解锁", "这一站，还在前方")
        layout.addWidget(label("先完成前面节点的题目，再来到这里。答错可以阅读解析后重试。"))
        layout.addWidget(button("回到当前学习节点", lambda: self.select_node(self.service.current_node().id)))
        layout.addStretch()
        return widget

    def start_quiz(self) -> None:
        if not self.service.can_quiz(self.viewed_id):
            self.start_learning()
            return
        try:
            questions = self.service.start_quiz(self.viewed_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "本轮题目未保存", f"{exc}\n请检查后重试，当前学习进度保留。")
            return
        self.quiz_index = next((i for i, q in enumerate(questions)
                                if q.id not in self.service.progress.answers
                                or not self.service.progress.answers[q.id].mastered), 0)
        self.show_panel("quiz")

    def start_learning(self) -> None:
        if self.player is not None and self.player.entering:
            return
        if not self.service.unlocked(self.viewed_id):
            self.show_panel("locked")
            return
        self._leave_learning()
        # Capture before changing window chrome so the old layout never flashes.
        route_snapshot = self.centralWidget().grab()
        self._set_learning_mode(True)
        node = self.service.node(self.viewed_id)
        player = LearningPlayer(self.service.lessons[node.id], node.name,
                                self.content_dir, self.scene_renderers,
                                music_enabled=self.music_enabled if self.music_player is not None else None)
        self.player = player
        player.back_requested.connect(lambda: self.show_panel("detail"))
        player.quiz_requested.connect(self._finish_learning)
        player.music_toggle_requested.connect(self.toggle_music)
        self.content_stack.addWidget(player)
        self.content_stack.setCurrentWidget(player)
        player.start(entrance_snapshot=route_snapshot)

    def _finish_learning(self) -> None:
        try:
            self.service.complete_lesson(self.viewed_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "学习记录未保存", f"{exc}\n请检查后重试，当前仍可查看学习小结。")
            return
        self.start_quiz()

    def _set_learning_mode(self, enabled: bool) -> None:
        """Hide window chrome during learning and restore the route window on exit."""
        self.header.setVisible(not enabled)
        self.route_footer.setVisible(not enabled)
        self.statusBar().setVisible(not enabled)
        self.route.set_map_visible(not enabled)
        if enabled:
            self._route_window_flags = self.windowFlags()
            self._route_geometry = self.geometry()
            self._route_maximized = self.isMaximized()
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        else:
            self.setWindowFlags(self._route_window_flags)
        if self._route_maximized:
            self.showMaximized()
        else:
            self.showNormal()
            self.setGeometry(self._route_geometry)
        self.activateWindow()
        if not enabled:
            QTimer.singleShot(0, self._layout_route_overlay)

    def _leave_learning(self, restore_window: bool = True) -> None:
        if self.player is not None:
            player = self.player
            self.player = None
            player.stop()
            self.content_stack.setCurrentIndex(0)
            self.content_stack.removeWidget(player)
            player.deleteLater()
            if restore_window:
                self._set_learning_mode(False)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if getattr(self, "player", None) is not None:
                self.player.pause()
        super().changeEvent(event)

    def closeEvent(self, event):
        self._leave_learning(restore_window=False)
        self.route.stop_animations()
        if self.music_player is not None:
            self.music_player.stop()
        super().closeEvent(event)

    def quiz_panel(self) -> QWidget:
        node = self.service.node(self.viewed_id)
        questions = self.service.questions_for(node.id)
        question = questions[self.quiz_index]
        widget, layout = self.new_panel(f"知识检验 · {self.quiz_index + 1}/{len(questions)}",
                                        node.name, "多选题：选中所有正确项" if question.kind == "multiple_choice"
                                        else "单选题 · 答错可重试，首次结果单独记录")
        layout.addWidget(label(question.prompt))
        self.answer_widget = self.question_views.build(question)
        layout.addWidget(self.answer_widget)
        self.feedback_label = label("")
        self.feedback_label.hide()
        layout.addWidget(self.feedback_label)
        self.submit_button = button("提交答案", self.submit_answer)
        layout.addWidget(self.submit_button)
        self.next_button = button("下一题" if self.quiz_index + 1 < len(questions)
                                  else "完成本段 · 返回路线", self.next_question)
        self.next_button.hide()
        layout.addWidget(self.next_button)
        layout.addWidget(button("返回故事", lambda: self.show_panel("detail"), True))
        layout.addStretch()
        return widget

    def submit_answer(self) -> None:
        node = self.service.node(self.viewed_id)
        question = self.service.questions_for(node.id)[self.quiz_index]
        try:
            result = self.service.submit(node.id, question.id, self.answer_widget.selected())
        except (ValueError, OSError) as exc:
            QMessageBox.warning(self, "本次未提交", str(exc))
            return
        message = "答对了。" if result.correct else "还没答对，请阅读解析后重新选择。"
        self.feedback_label.setText(message + "\n\n" + result.explanation)
        self.feedback_label.setObjectName("feedbackOk" if result.correct else "feedbackNo")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)
        self.feedback_label.show()
        if result.correct:
            self.submit_button.setEnabled(False)
            self.answer_widget.setEnabled(False)
            self.next_button.show()
        self.refresh()

    def next_question(self) -> None:
        if self.quiz_index + 1 < len(self.service.questions_for(self.viewed_id)):
            self.quiz_index += 1
            self.show_panel("quiz")
        else:
            self.show_panel("detail")

    def summary_panel(self) -> QWidget:
        summary = self.service.summary()
        finished = summary.completed_nodes == summary.total_nodes
        widget, layout = self.new_panel("学习回顾",
                                        "向长征英烈献花" if finished else "每一步，都留下收获",
                                        "完成全部节点，献上一束花，致敬长征途中牺牲的英烈。"
                                        if finished else "完成全部节点后，将开放献花纪念。")
        if finished:
            layout.addWidget(label(f"{summary.completed_nodes} / {summary.total_nodes} 个节点已完成", "muted"))
            layout.addWidget(button("进入献花纪念", self.show_memorial))
        else:
            for title, value in [("已完成节点", f"{summary.completed_nodes} / {summary.total_nodes}"),
                                  ("首次答对", f"{summary.first_correct} / {summary.total_questions}"),
                                  ("已掌握题目", f"{summary.mastered_questions} / {summary.total_questions}")]:
                layout.addWidget(label(title, "section"))
                layout.addWidget(label(value, "title"))
            layout.addWidget(label("首次结果保留最初作答情况；通过重试掌握题目后可以继续学习。", "muted"))
        layout.addWidget(button("回到学习路线", lambda: self.select_node(self.service.current_node().id), True))
        layout.addStretch()
        return widget

    def show_memorial(self) -> None:
        summary = self.service.summary()
        if summary.completed_nodes != summary.total_nodes:
            return
        if self.memorial_window is not None and self.memorial_window.isVisible():
            self.memorial_window.raise_()
            return
        import json
        martyrs = json.loads((self.assets_dir / "content" / "martyrs.json").read_text(encoding="utf-8"))
        self.memorial_window = MemorialWindow(
            martyrs, self.assets_dir / "images" / "memorial", self)
        self.memorial_window.finished.connect(self._memorial_finished)
        self.route.stop_animations()
        central = self.centralWidget()
        self._route_opacity = QGraphicsOpacityEffect(central)
        central.setGraphicsEffect(self._route_opacity)
        self._route_opacity.setOpacity(1.0)
        self._route_transition = QPropertyAnimation(self._route_opacity, b"opacity", self)
        self._route_transition.setDuration(260)
        self._route_transition.setStartValue(1.0)
        self._route_transition.setEndValue(0.0)
        self._route_transition.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._route_transition.finished.connect(self._open_memorial_window)
        self._route_transition.start()

    def _open_memorial_window(self) -> None:
        if self.memorial_window is None:
            return
        self.memorial_window.show()
        self.memorial_window.raise_()
        self.memorial_window.activateWindow()
        self._route_transition = QPropertyAnimation(
            self.memorial_window, b"windowOpacity", self)
        self._route_transition.setDuration(500)
        self._route_transition.setStartValue(0.0)
        self._route_transition.setEndValue(1.0)
        self._route_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._route_transition.start()

    def _memorial_finished(self, result: int) -> None:
        if self.memorial_window is not None:
            self.memorial_window.deleteLater()
            self.memorial_window = None
        if self._route_opacity is None:
            return
        self._route_transition = QPropertyAnimation(self._route_opacity, b"opacity", self)
        self._route_transition.setDuration(300)
        self._route_transition.setStartValue(0.0)
        self._route_transition.setEndValue(1.0)
        self._route_transition.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._route_transition.finished.connect(self._restore_route_opacity)
        self._route_transition.start()

    def _restore_route_opacity(self) -> None:
        central = self.centralWidget()
        if central is not None:
            central.setGraphicsEffect(None)
        self._route_opacity = None

    def confirm_reset(self) -> None:
        if QMessageBox.question(self, "重新出发", "清空本内容包的学习进度，重新开始？",
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.service.reset()
        except OSError as exc:
            QMessageBox.warning(self, "无法重置", str(exc))
            return
        self.select_node(self.service.current_node().id)

    def about_panel(self) -> QWidget:
        widget, layout = self.new_panel("使用与来源", "让每一段学习有据可查")
        layout.addWidget(label(self.service.pack.scope))
        layout.addWidget(label("使用方法", "section"))
        if self.service.pack.quiz_size is not None:
            layout.addWidget(label(f"每章随机抽取{self.service.pack.quiz_size}题（题库不足时使用全部题目），同时打乱选项。"
                                  "本轮抽题与选项顺序保存在本机，重试、返回和重启不会换题。完成本轮全部题目后解锁下一章，"
                                  "复习沿用本轮，重新出发后重新抽取。"))
        layout.addWidget(label("点击路线节点，选择开始本段学习。过场自动播放，点击文字框或按右方向键翻页，左方向键回看，空格暂停或继续；切出窗口会暂停，点击文字框继续。小结出现后点击文字框或按回车确认答题，R键重看整段，右上角退出或Esc返回路线。长文字可在框内滚动阅读。学过的节点可重看或直接答题，进度自动保存在本机。"))
        layout.addWidget(label("内容状态", "section"))
        layout.addWidget(label("预览内容，史实、措辞和资料出处待团队核验。" if self.service.pack.review_status == "draft"
                               else "历史内容与参考资料由参赛团队维护。"))
        layout.addWidget(label("开发与素材", "section"))
        layout.addWidget(label("主界面使用AI辅助创作的山水背景；交互路线、节点和通关描线动画由Qt独立绘制。图像为美术复原，学习路线不代表精确地理路径。使用Python、PySide6 Essentials及PyInstaller；第三方许可说明随交付提供。内容核验和最终验收由团队完成。"))
        layout.addWidget(button("继续学习", lambda: self.select_node(self.service.current_node().id)))
        layout.addStretch()
        return widget
