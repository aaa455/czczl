"""Random rounds must survive restart, enforce the drawn subset and save atomically."""
from dataclasses import replace
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from app.content import JsonContentRepository
from app.learning import LearningService, content_signature
from app.storage import JsonProgressStore

CONTENT = Path(__file__).resolve().parents[1] / "assets/content"


class RandomQuizTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.pack = JsonContentRepository(CONTENT).load()
        self.store = JsonProgressStore(Path(self.tmp.name) / "progress.json")
        self.service = LearningService(self.pack, self.store, rng=random.Random(23))
        self.node = self.pack.nodes[0]

    def start(self):
        self.service.complete_lesson(self.node.id)
        return self.service.start_quiz(self.node.id)

    def test_ten_distinct_draws_and_option_permutations_survive_restart(self):
        self.assertEqual(self.service.questions_for(self.node.id), ())
        self.assertFalse(self.service.completed(self.node.id))
        questions = self.start()
        self.assertEqual(len(questions), 10)
        self.assertEqual(len({q.id for q in questions}), 10)
        originals = {q.id: q for q in self.node.questions}
        self.assertTrue(any(q.options != originals[q.id].options for q in questions))
        for q in questions:
            self.assertEqual({o.id: o.text for o in q.options}, {o.id: o.text for o in originals[q.id].options})
            self.assertEqual(q.answer, originals[q.id].answer)
        self.assertEqual(self.service.start_quiz(self.node.id), questions)
        reloaded = LearningService(self.pack, self.store, rng=random.Random(99))
        self.assertEqual(reloaded.start_quiz(self.node.id), questions)
        self.assertEqual(reloaded.progress.quiz_sessions, self.service.progress.quiz_sessions)

    def test_sampled_ten_unlock_next_and_statistics_use_eighty_not_bank(self):
        questions = self.start()
        for q in questions[:-1]:
            self.service.submit(self.node.id, q.id, q.answer)
        self.assertFalse(self.service.unlocked(self.pack.nodes[1].id))
        result = self.service.submit(self.node.id, questions[-1].id, questions[-1].answer)
        self.assertTrue(result.node_completed)
        self.assertTrue(self.service.unlocked(self.pack.nodes[1].id))
        self.assertEqual(len(self.service.progress.answers), 10)
        summary = self.service.summary()
        self.assertEqual(summary.total_questions, 80)
        self.assertEqual(summary.mastered_questions, 10)
        self.assertEqual(summary.first_correct, 10)
        self.assertEqual(summary.completed_nodes, 1)

    def test_unsampled_question_and_locked_draw_are_rejected(self):
        drawn = {q.id for q in self.start()}
        other = next(q for q in self.node.questions if q.id not in drawn)
        with self.assertRaisesRegex(ValueError, "本轮"):
            self.service.submit(self.node.id, other.id, other.answer)
        with self.assertRaisesRegex(ValueError, "前面"):
            self.service.start_quiz(self.pack.nodes[1].id)
        self.assertEqual(self.service.progress.answers, {})

    def test_no_draw_before_learning_and_failed_draw_keeps_disk_and_memory(self):
        with self.assertRaises(ValueError):
            self.service.start_quiz(self.node.id)
        self.service.complete_lesson(self.node.id)
        before = self.store.path.read_bytes()
        with patch.object(self.store, "save", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                self.service.start_quiz(self.node.id)
        self.assertEqual(self.service.progress.quiz_sessions, {})
        self.assertEqual(self.store.path.read_bytes(), before)
        self.assertEqual(len(self.service.start_quiz(self.node.id)), 10)

    def test_wrong_answer_retry_preserves_draw_first_result_and_multiple_choice(self):
        questions = self.start()
        q = questions[0]
        wrong = next(o.id for o in q.options if o.id not in q.answer)
        self.assertFalse(self.service.submit(self.node.id, q.id, (wrong,)).correct)
        self.assertTrue(self.service.submit(self.node.id, q.id, tuple(reversed(q.answer))).correct)
        self.assertEqual(self.service.start_quiz(self.node.id), questions)
        self.assertEqual(self.service.summary().first_correct, 0)
        self.assertEqual(self.service.summary().mastered_questions, 1)
        multi = next(q for q in self.node.questions if q.kind == "multiple_choice")
        pack = replace(self.pack, nodes=(replace(self.node, questions=(multi,)),), quiz_size=10)
        service = LearningService(pack, JsonProgressStore(Path(self.tmp.name) / "multi.json"), rng=random.Random(1))
        service.complete_lesson(self.node.id)
        q = service.start_quiz(self.node.id)[0]
        self.assertFalse(service.submit(self.node.id, q.id, (q.answer[0],)).correct)
        self.assertTrue(service.submit(self.node.id, q.id, tuple(reversed(q.answer))).correct)

    def test_small_external_bank_uses_all_and_reset_allows_new_round(self):
        pack = replace(self.pack, nodes=(replace(self.node, questions=self.node.questions[:3]),))
        service = LearningService(pack, JsonProgressStore(Path(self.tmp.name) / "small.json"), rng=random.Random(1))
        service.complete_lesson(self.node.id)
        self.assertEqual(len(service.start_quiz(self.node.id)), 3)
        self.assertEqual(service.summary().total_questions, 3)
        first = self.start()
        self.service.reset()
        self.assertEqual(self.service.progress.quiz_sessions, {})
        self.assertEqual(self.service.progress.answers, {})
        second = self.start()
        self.assertNotEqual(first, second)

    def test_legacy_progress_without_sessions_and_quiz_rule_changes(self):
        pack = replace(self.pack, quiz_size=None)
        path = Path(self.tmp.name) / "legacy.json"
        path.write_text(json.dumps({"schema_version": 1, "pack_id": pack.id,
            "content_signature": content_signature(pack), "answers": {}}), encoding="utf-8")
        legacy = LearningService(pack, JsonProgressStore(path))
        legacy.complete_lesson(self.node.id)
        self.assertEqual(legacy.start_quiz(self.node.id), self.node.questions)
        self.assertEqual(legacy.progress.quiz_sessions, {})
        self.assertNotEqual(content_signature(pack), content_signature(self.pack))
        enabled = LearningService(self.pack, JsonProgressStore(path))
        self.assertEqual(enabled.progress.quiz_sessions, {})
        self.assertEqual(len(list(path.parent.glob("legacy.*.json"))), 1)

    def test_corrupt_or_mismatched_sessions_do_not_silently_redraw(self):
        self.start()
        raw = json.loads(self.store.path.read_text(encoding="utf-8"))
        original = json.dumps(raw)
        session = raw["quiz_sessions"][self.node.id]
        session["question_ids"].append(session["question_ids"][0])
        self.store.path.write_text(json.dumps(raw), encoding="utf-8")
        restored = LearningService(self.pack, self.store)
        self.assertEqual(restored.progress.quiz_sessions, {})
        self.assertEqual(len(list(self.store.path.parent.glob("progress.*.json"))), 1)
        raw = json.loads(original)
        session = raw["quiz_sessions"][self.node.id]
        qid = session["question_ids"][0]
        session["option_orders"][qid][0] = "not-in-the-question"
        self.store.path.write_text(json.dumps(raw), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "选项顺序记录"):
            LearningService(self.pack, self.store)


if __name__ == "__main__":
    unittest.main()
