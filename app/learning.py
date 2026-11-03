"""Learning rules, deliberately independent of Qt and disk storage."""
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
import random

from app.lessons import lesson_signature, placeholder_lesson
from app.models import (AnswerResult, Attempt, ContentPack, LearningSummary,
                        Lesson, Node, ProgressStore, Question, QuizSession)

Evaluator = Callable[[Question, tuple[str, ...]], bool]


class QuestionRegistry:
    def __init__(self):
        self._evaluators: dict[str, Evaluator] = {}

    def register(self, kind: str, evaluator: Evaluator) -> None:
        if kind in self._evaluators:
            raise ValueError(f"题型重复注册：{kind}")
        self._evaluators[kind] = evaluator

    def evaluate(self, question: Question, selected: tuple[str, ...]) -> bool:
        return self._evaluators[question.kind](question, selected)

    def supports(self, kind: str) -> bool:
        return kind in self._evaluators


def default_registry() -> QuestionRegistry:
    registry = QuestionRegistry()
    registry.register("single_choice", lambda q, s: len(s) == 1 and s == q.answer)
    registry.register("multiple_choice", lambda q, s: set(s) == set(q.answer))
    return registry


def content_signature(pack: ContentPack) -> str:
    # Prose/style edits preserve progress; changed rules/options/order invalidate it safely.
    rules = [(n.id, [(q.id, q.kind, q.prompt, [asdict(o) for o in q.options], q.answer)
                     for q in n.questions]) for n in pack.nodes]
    if pack.quiz_size is not None:
        rules = {"nodes": rules, "quiz_size": pack.quiz_size, "shuffle_options": True}
    return hashlib.sha256(json.dumps(rules, ensure_ascii=False).encode("utf-8")).hexdigest()


class LearningService:
    def __init__(self, pack: ContentPack, store: ProgressStore,
                 registry: QuestionRegistry | None = None,
                 lessons: dict[str, Lesson] | None = None,
                 rng: random.Random | None = None):
        self.pack, self.store = pack, store
        self.registry = registry or default_registry()
        self.rng = rng if rng is not None else random.SystemRandom()
        self.lessons = {n.id: placeholder_lesson(n) for n in pack.nodes}
        if lessons is not None:
            self.lessons.update(lessons)
        for node in pack.nodes:
            for question in node.questions:
                if not self.registry.supports(question.kind):
                    raise ValueError(f"尚未注册题型：{question.kind}")
        self.signature = content_signature(pack)
        self.progress = store.load(pack.id, self.signature)
        self._validate_sessions()

    def _validate_sessions(self) -> None:
        nodes = {n.id: n for n in self.pack.nodes}
        for node_id, session in self.progress.quiz_sessions.items():
            if node_id not in nodes:
                raise ValueError("抽题记录与章节不匹配，请使用新的演示存档目录")
            bank = {q.id: q for q in nodes[node_id].questions}
            if (len(session.question_ids) != self.quiz_count(node_id)
                    or not set(session.question_ids) <= set(bank)):
                raise ValueError("抽题记录与题库不匹配，请使用新的演示存档目录")
            for qid in session.question_ids:
                if set(session.option_orders[qid]) != {o.id for o in bank[qid].options}:
                    raise ValueError("选项顺序记录与题库不匹配，请使用新的演示存档目录")

    def node(self, node_id: str) -> Node:
        return next(n for n in self.pack.nodes if n.id == node_id)

    def quiz_count(self, node_id: str) -> int:
        count = len(self.node(node_id).questions)
        return min(self.pack.quiz_size, count) if self.pack.quiz_size is not None else count

    def questions_for(self, node_id: str) -> tuple[Question, ...]:
        """Read the current round without drawing or mutating progress."""
        node = self.node(node_id)
        if self.pack.quiz_size is None:
            return node.questions
        session = self.progress.quiz_sessions.get(node_id)
        if session is None:
            return ()
        bank = {q.id: q for q in node.questions}
        result = []
        for qid in session.question_ids:
            question = bank[qid]
            options = {o.id: o for o in question.options}
            result.append(replace(question, options=tuple(options[oid] for oid in session.option_orders[qid])))
        return tuple(result)

    def start_quiz(self, node_id: str) -> tuple[Question, ...]:
        if not self.can_quiz(node_id):
            raise ValueError("请先完成前面的节点及本段学习")
        if self.pack.quiz_size is None or node_id in self.progress.quiz_sessions:
            return self.questions_for(node_id)
        selected = self.rng.sample(self.node(node_id).questions, self.quiz_count(node_id))
        orders = {q.id: tuple(o.id for o in self.rng.sample(q.options, len(q.options))) for q in selected}
        updated = deepcopy(self.progress)
        updated.quiz_sessions[node_id] = QuizSession(tuple(q.id for q in selected), orders)
        # Save the draw before exposing it; retries and relaunches reuse this round.
        self.store.save(updated)
        self.progress = updated
        return self.questions_for(node_id)

    def completed(self, node_id: str) -> bool:
        questions = self.questions_for(node_id)
        return bool(questions) and all(self.progress.answers.get(q.id) is not None
                   and self.progress.answers[q.id].mastered
                   for q in questions)

    def unlocked(self, node_id: str) -> bool:
        for node in self.pack.nodes:
            if node.id == node_id:
                return True
            if not self.completed(node.id):
                return False
        return False

    def current_node(self) -> Node:
        return next((n for n in self.pack.nodes if not self.completed(n.id)),
                    self.pack.nodes[-1])

    def lesson_learned(self, node_id: str) -> bool:
        return self.progress.learned_lessons.get(node_id) == lesson_signature(self.lessons[node_id])

    def complete_lesson(self, node_id: str) -> None:
        if not self.unlocked(node_id):
            raise ValueError("请先完成前面的学习节点")
        updated = deepcopy(self.progress)
        updated.learned_lessons[node_id] = lesson_signature(self.lessons[node_id])
        self.store.save(updated)
        self.progress = updated

    def can_quiz(self, node_id: str) -> bool:
        # Previously completed nodes remain available for review after upgrading.
        return self.unlocked(node_id) and (self.lesson_learned(node_id) or self.completed(node_id))

    def submit(self, node_id: str, question_id: str,
               selected: tuple[str, ...]) -> AnswerResult:
        if not self.unlocked(node_id):
            raise ValueError("请先完成前面的学习节点")
        if not self.can_quiz(node_id):
            raise ValueError("请先完成本段学习，再开始答题")
        question = next((q for q in self.questions_for(node_id) if q.id == question_id), None)
        if question is None:
            raise ValueError("题目不在本轮答题列表中")
        valid = {o.id for o in question.options}
        if (not selected or len(set(selected)) != len(selected)
                or not set(selected) <= valid
                or (question.kind == "single_choice" and len(selected) != 1)):
            raise ValueError("请选择有效答案")
        correct = self.registry.evaluate(question, selected)
        updated = deepcopy(self.progress)
        previous = updated.answers.get(question_id)
        first = previous is None
        updated.answers[question_id] = Attempt(
            correct if first else previous.first_correct,
            correct or (previous.mastered if previous else False),
            1 if first else previous.submissions + 1,
        )
        # Persist first: a failed write must not silently advance the visible state.
        self.store.save(updated)
        self.progress = updated
        return AnswerResult(correct, first, question.explanation, self.completed(node_id))

    def reset(self) -> None:
        from app.models import Progress
        fresh = Progress(self.pack.id, self.signature)
        self.store.save(fresh)
        self.progress = fresh

    def summary(self) -> LearningSummary:
        selected_ids = {q.id for n in self.pack.nodes for q in self.questions_for(n.id)}
        attempts = [a for qid, a in self.progress.answers.items() if qid in selected_ids]
        return LearningSummary(sum(self.completed(n.id) for n in self.pack.nodes),
                               len(self.pack.nodes), sum(a.first_correct for a in attempts),
                               sum(self.quiz_count(n.id) for n in self.pack.nodes),
                               sum(a.mastered for a in attempts))
