"""Native shell and replaceable right-hand panels."""
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (QFileDialog, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget)

from app.learning import LearningService
from app.ui.badge import BadgeExporter, PngBadgeExporter
from app.ui.questions import QuestionViewRegistry, default_views
from app.ui.route_map import RouteMap
from app.ui.lesson_player import LearningPlayer, SceneRendererRegistry, default_scene_renderers


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
                 badge_exporter: BadgeExporter | None = None,
                 content_dir: Path | None = None,
                 scene_renderers: SceneRendererRegistry | None = None):
        super().__init__()
        self.service = service
        self.question_views = question_views or default_views()
        self.badge_exporter = badge_exporter or PngBadgeExporter()
        self.content_dir = content_dir or Path(__file__).resolve().parents[2] / "assets/content"
        self.scene_renderers = scene_renderers or default_scene_renderers()
        self.player: LearningPlayer | None = None
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
        root = QWidget()
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        header = QFrame()
        header.setObjectName("header")
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
        self.meter = label("", "section")
        self.meter.setWordWrap(False)
        header_layout.addWidget(self.meter)
        header_layout.addSpacing(15)
        header_layout.addWidget(button("学习回顾", lambda: self.show_panel("summary"), True))
        header_layout.addWidget(button("使用与来源", lambda: self.show_panel("about"), True))
        header_layout.addWidget(button("重新出发", self.confirm_reset, True))
        root_layout.addWidget(header)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        left = QWidget()
        left.setMinimumWidth(530)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(26, 23, 16, 18)
        left_layout.addWidget(label("THE LONG MARCH · 学习之旅", "eyebrow"))
        left_layout.addWidget(label("循着足迹，走进历史", "hero"))
        left_layout.addWidget(label("阅读一段历史，完成一次思考，点亮下一站。", "muted"))
        self.route = RouteMap(service)
        self.route.node_clicked.connect(self.select_node)
        left_layout.addWidget(self.route, 1)
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(False)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(label("学习路线示意 · 合并节点为主题概括 · 连线不代表精确地理路径或实际里程", "muted"))
        station_grid = QGridLayout()
        self.station_buttons = []
        for i, node in enumerate(service.pack.nodes):
            item = button(f"{i + 1}. {node.short_name}",
                          lambda nid=node.id: self.select_node(nid), True)
            item.setAccessibleName(f"查看第{i + 1}站：{node.name}")
            station_grid.addWidget(item, i // 4, i % 4)
            self.station_buttons.append(item)
        left_layout.addLayout(station_grid)
        splitter.addWidget(left)
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(410)
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        panel_layout.addWidget(self.scroll)
        splitter.addWidget(panel)
        splitter.setSizes([760, 440])
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(splitter)
        root_layout.addWidget(self.content_stack, 1)
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

    def register_panel(self, name: str, factory: Callable[[], QWidget]) -> None:
        if name in self._panels:
            raise ValueError(f"面板重复注册：{name}")
        self._panels[name] = factory

    def show_panel(self, name: str) -> None:
        self._leave_learning()
        if name == "quiz" and not self.service.can_quiz(self.viewed_id):
            self.start_learning()
            return
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
        self.meter.setText(f"已完成 {summary.completed_nodes}/{summary.total_nodes} 站\n"
                           f"首次答对 {summary.first_correct}/{summary.total_questions}")
        self.progress_bar.setRange(0, summary.total_nodes)
        self.progress_bar.setValue(summary.completed_nodes)
        for item, node in zip(self.station_buttons, self.service.pack.nodes):
            state = "已完成" if self.service.completed(node.id) else (
                "可学习" if self.service.unlocked(node.id) else "未解锁")
            item.setToolTip(f"{node.name} · {state}")
        self.route.selected = self.viewed_id
        self.route.update()

    def select_node(self, node_id: str) -> None:
        self.viewed_id = node_id
        self.refresh()
        self.show_panel("detail" if self.service.unlocked(node_id) else "locked")

    def detail_panel(self) -> QWidget:
        node = self.service.node(self.viewed_id)
        index = self.service.pack.nodes.index(node)
        widget, layout = self.new_panel(f"第 {index + 1} 站 / 共 {len(self.service.pack.nodes)} 站",
                                        node.name, f"{node.time}\n{node.place}")
        for title, content in [("发生了什么", node.event), ("精神内核", node.spirit),
                               ("新程对照", node.modern), ("史料出处", "\n".join(node.sources))]:
            layout.addWidget(label(title, "section"))
            layout.addWidget(label(content, "muted" if title == "史料出处" else "body"))
        complete = self.service.completed(node.id)
        layout.addWidget(button("重新观看本段学习" if self.service.lesson_learned(node.id)
                                else "开始本段学习", self.start_learning))
        if self.service.can_quiz(node.id):
            layout.addWidget(button("复习本段题目" if complete else "继续答题", self.start_quiz, True))
        if complete:
            if index < len(self.service.pack.nodes) - 1:
                next_id = self.service.pack.nodes[index + 1].id
                layout.addWidget(button("继续前进 · 下一站", lambda: self.select_node(next_id), True))
            else:
                layout.addWidget(button("查看学习回顾 · 领取徽章", lambda: self.show_panel("summary"), True))
        layout.addStretch()
        return widget

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
        questions = self.service.node(self.viewed_id).questions
        self.quiz_index = next((i for i, q in enumerate(questions)
                                if q.id not in self.service.progress.answers
                                or not self.service.progress.answers[q.id].mastered), 0)
        self.show_panel("quiz")

    def start_learning(self) -> None:
        if not self.service.unlocked(self.viewed_id):
            self.show_panel("locked")
            return
        self._leave_learning()
        node = self.service.node(self.viewed_id)
        player = LearningPlayer(self.service.lessons[node.id], node.name,
                                self.content_dir, self.scene_renderers)
        self.player = player
        player.back_requested.connect(lambda: self.show_panel("detail"))
        player.quiz_requested.connect(self._finish_learning)
        self.content_stack.addWidget(player)
        self.content_stack.setCurrentWidget(player)
        player.start()

    def _finish_learning(self) -> None:
        try:
            self.service.complete_lesson(self.viewed_id)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "学习记录未保存", f"{exc}\n请检查后重试，当前仍可查看学习小结。")
            return
        self.start_quiz()

    def _leave_learning(self) -> None:
        if self.player is not None:
            player = self.player
            self.player = None
            player.stop()
            self.content_stack.setCurrentIndex(0)
            self.content_stack.removeWidget(player)
            player.deleteLater()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow():
            if getattr(self, "player", None) is not None:
                self.player.pause()
        super().changeEvent(event)

    def closeEvent(self, event):
        self._leave_learning()
        super().closeEvent(event)

    def quiz_panel(self) -> QWidget:
        node = self.service.node(self.viewed_id)
        question = node.questions[self.quiz_index]
        widget, layout = self.new_panel(f"知识检验 · {self.quiz_index + 1}/{len(node.questions)}",
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
        self.next_button = button("下一题" if self.quiz_index + 1 < len(node.questions)
                                  else "完成本段 · 返回路线", self.next_question)
        self.next_button.hide()
        layout.addWidget(self.next_button)
        layout.addWidget(button("返回故事", lambda: self.show_panel("detail"), True))
        layout.addStretch()
        return widget

    def submit_answer(self) -> None:
        node = self.service.node(self.viewed_id)
        question = node.questions[self.quiz_index]
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
        if self.quiz_index + 1 < len(self.service.node(self.viewed_id).questions):
            self.quiz_index += 1
            self.show_panel("quiz")
        else:
            self.show_panel("detail")

    def summary_panel(self) -> QWidget:
        summary = self.service.summary()
        finished = summary.completed_nodes == summary.total_nodes
        widget, layout = self.new_panel("学习回顾", "每一步，都留下收获",
                                        "完成全部节点后，可以保存专属学习纪念徽章。")
        for title, value in [("已完成节点", f"{summary.completed_nodes} / {summary.total_nodes}"),
                              ("首次答对", f"{summary.first_correct} / {summary.total_questions}"),
                              ("已掌握题目", f"{summary.mastered_questions} / {summary.total_questions}")]:
            layout.addWidget(label(title, "section"))
            layout.addWidget(label(value, "title"))
        layout.addWidget(label("首次结果保留最初作答情况；通过重试掌握题目后可以继续学习。", "muted"))
        self.badge_name = QLineEdit()
        self.badge_name.setPlaceholderText("你的名字（最多12字，可不填写）")
        self.badge_name.setMaxLength(12)
        self.badge_name.setAccessibleName("纪念徽章上的名字")
        layout.addWidget(self.badge_name)
        export_button = button("保存学习纪念徽章 PNG", self.export_badge)
        export_button.setEnabled(finished)
        layout.addWidget(export_button)
        layout.addWidget(button("回到学习路线", lambda: self.select_node(self.service.current_node().id), True))
        layout.addStretch()
        return widget

    def export_badge(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "保存学习纪念徽章", "足迹长征-学习徽章.png", "PNG图片 (*.png)")
        if not path:
            return
        try:
            target = Path(path)
            if target.suffix.lower() != ".png":
                target = target.with_suffix(".png")
            self.badge_exporter.export(target, self.badge_name.text(), self.service.summary())
            QMessageBox.information(self, "保存成功", f"徽章已保存到：\n{target}")
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法保存", str(exc))

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
        layout.addWidget(label("点击路线节点，选择开始本段学习。过场支持暂停、手动翻页与自动翻页；查看小结后确认进入答题。学过的节点可重看或直接答题。答错可重试，进度自动保存在本机。"))
        layout.addWidget(label("内容状态", "section"))
        layout.addWidget(label("预览内容，史实、措辞和资料出处待团队核验。" if self.service.pack.review_status == "draft"
                               else "具体资料出处见各节点，内容由参赛团队维护。"))
        layout.addWidget(label("开发与素材", "section"))
        layout.addWidget(label("界面与路线图使用Qt原生组件和程序绘图。使用Python、PySide6 Essentials及PyInstaller；第三方许可说明随交付提供。开发过程使用AI辅助，内容核验和最终验收由团队完成。"))
        layout.addWidget(button("继续学习", lambda: self.select_node(self.service.current_node().id)))
        layout.addStretch()
        return widget
