from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.content import ContentError, JsonContentRepository
from app.learning import LearningService, content_signature, default_registry
from app.models import Attempt, Progress
from app.storage import JsonProgressStore

CONTENT = Path(__file__).resolve().parents[1] / "assets" / "content"


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "progress.json"
        self.store = JsonProgressStore(self.path)
        pack = JsonContentRepository(CONTENT).load()
        # Keep the original rule tests independent of the evolving production bank.
        self.pack = replace(pack, quiz_size=None,
                            nodes=tuple(replace(n, questions=n.questions[:2]) for n in pack.nodes))
        self.service = LearningService(self.pack, self.store)
        self.service.complete_lesson(self.pack.nodes[0].id)

    def finish_node(self, node):
        self.service.complete_lesson(node.id)
        for question in node.questions:
            self.service.submit(node.id, question.id, question.answer)

    def test_locked_node_cannot_be_answered(self):
        node = self.pack.nodes[1]
        with self.assertRaisesRegex(ValueError, "前面"):
            self.service.submit(node.id, node.questions[0].id, node.questions[0].answer)
        self.assertEqual(self.service.progress.answers, {})

    def test_retry_preserves_first_result_and_does_not_double_count(self):
        node = self.pack.nodes[0]
        question = node.questions[0]
        wrong = next(o.id for o in question.options if o.id not in question.answer)
        result = self.service.submit(node.id, question.id, (wrong,))
        self.assertFalse(result.correct)
        self.assertFalse(self.service.unlocked(self.pack.nodes[1].id))
        self.service.submit(node.id, question.id, question.answer)
        self.service.submit(node.id, question.id, question.answer)
        self.assertEqual(self.service.summary().first_correct, 0)
        self.assertEqual(self.service.summary().mastered_questions, 1)
        self.finish_node(node)
        self.assertTrue(self.service.unlocked(self.pack.nodes[1].id))
        self.assertEqual(self.service.summary().first_correct, len(node.questions) - 1)

    def test_all_nodes_complete_restart_and_review(self):
        for node in self.pack.nodes:
            self.finish_node(node)
        summary = self.service.summary()
        self.assertEqual(summary.completed_nodes, len(self.pack.nodes))
        self.assertEqual(summary.first_correct, sum(len(n.questions) for n in self.pack.nodes))
        reloaded = LearningService(self.pack, JsonProgressStore(self.path))
        self.assertEqual(reloaded.summary(), summary)
        question = self.pack.nodes[0].questions[0]
        wrong = next(o.id for o in question.options if o.id not in question.answer)
        reloaded.submit(self.pack.nodes[0].id, question.id, (wrong,))
        self.assertEqual(reloaded.summary(), summary)

    def test_no_hardcoded_node_ids_or_two_question_limit(self):
        node = self.pack.nodes[0]
        extra = replace(node.questions[0], id="extra-question")
        custom = replace(self.pack, nodes=(replace(node, id="non-numeric-node",
                                                   questions=(*node.questions, extra)),))
        self.service = LearningService(custom, self.store)
        self.finish_node(custom.nodes[0])
        self.assertEqual(self.service.summary().total_questions, 3)
        self.assertEqual(self.service.summary().completed_nodes, 1)

    def test_invalid_choices_leave_state_unchanged(self):
        node = self.pack.nodes[0]
        q = node.questions[0]
        for choice in [(), ("not-an-option",), (q.answer[0], q.answer[0]), ("a", "b")]:
            with self.assertRaises(ValueError):
                self.service.submit(node.id, q.id, choice)
        self.assertEqual(self.service.summary().mastered_questions, 0)

    def test_write_failure_does_not_advance_memory(self):
        node = self.pack.nodes[0]
        with patch.object(self.store, "save", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                self.service.submit(node.id, node.questions[0].id, node.questions[0].answer)
        self.assertEqual(self.service.progress.answers, {})

    def test_corrupt_save_preserved_before_recovery(self):
        self.path.write_text("broken save", encoding="utf-8")
        restored = LearningService(self.pack, self.store)
        self.assertEqual(restored.progress.answers, {})
        backups = list(self.path.parent.glob("progress.*.json"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding="utf-8"), "broken save")
        self.assertTrue(self.store.notice)

    def test_rule_change_archives_save_but_prose_change_preserves_signature(self):
        self.finish_node(self.pack.nodes[0])
        node = self.pack.nodes[0]
        prose = replace(self.pack, nodes=(replace(node, event="New prose"), *self.pack.nodes[1:]))
        self.assertEqual(content_signature(prose), content_signature(self.pack))
        wrong = next(o.id for o in node.questions[0].options if o.id not in node.questions[0].answer)
        question = replace(node.questions[0], answer=(wrong,))
        changed = replace(self.pack, nodes=(replace(node, questions=(question, *node.questions[1:])),
                                           *self.pack.nodes[1:]))
        updated = LearningService(changed, self.store)
        self.assertEqual(updated.progress.answers, {})
        self.assertEqual(len(list(self.path.parent.glob("progress.*.json"))), 1)

    def test_multiple_choice_and_custom_evaluator(self):
        node = self.pack.nodes[0]
        question = replace(node.questions[0], kind="multiple_choice", answer=("a", "b"))
        pack = replace(self.pack, nodes=(replace(node, questions=(question,)),))
        service = LearningService(pack, self.store)
        service.complete_lesson(node.id)
        self.assertFalse(service.submit(node.id, question.id, ("a",)).correct)
        self.assertTrue(service.submit(node.id, question.id, ("b", "a")).correct)
        registry = default_registry()
        registry.register("custom", lambda q, selected: selected == ("c",))
        custom_q = replace(question, kind="custom")
        custom_pack = replace(pack, nodes=(replace(node, questions=(custom_q,)),))
        custom = LearningService(custom_pack, self.store, registry)
        custom.complete_lesson(node.id)
        self.assertTrue(custom.submit(node.id, question.id, ("c",)).correct)

    def test_reset_persists(self):
        self.finish_node(self.pack.nodes[0])
        self.service.reset()
        self.assertEqual(LearningService(self.pack, self.store).summary().completed_nodes, 0)

    def test_atomic_write_failure_keeps_previous_file(self):
        self.finish_node(self.pack.nodes[0])
        previous = self.path.read_bytes()
        with patch("app.storage.os.replace", side_effect=OSError("cannot replace")):
            with self.assertRaises(OSError):
                self.store.save(Progress(self.pack.id, self.service.signature))
        self.assertEqual(self.path.read_bytes(), previous)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


class ContentTests(unittest.TestCase):
    def check_invalid(self, modify):
        with tempfile.TemporaryDirectory() as tmp:
            raw = json.loads((CONTENT / "nodes.json").read_text(encoding="utf-8"))
            modify(raw)
            Path(tmp, "nodes.json").write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ContentError):
                JsonContentRepository(Path(tmp)).load()

    def test_duplicate_node(self):
        self.check_invalid(lambda raw: raw["nodes"].append(raw["nodes"][0]))

    def test_duplicate_question(self):
        self.check_invalid(lambda raw: raw["nodes"][0]["questions"].append(raw["nodes"][0]["questions"][0]))

    def test_invalid_answer(self):
        self.check_invalid(lambda raw: raw["nodes"][0]["questions"][0].update(answer=["missing"]))

    def test_invalid_position(self):
        self.check_invalid(lambda raw: raw["nodes"][0].update(position=[True, 0.5]))

    def test_invalid_quiz_size(self):
        for value in [True, 0, -1, "10", 2.5]:
            with self.subTest(value=value):
                self.check_invalid(lambda raw: raw.update(quiz_size=value))

    def test_missing_source(self):
        self.check_invalid(lambda raw: raw["nodes"][0].update(sources=[]))

    def test_package_id_cannot_escape_save_directory(self):
        self.check_invalid(lambda raw: raw.update(id="../outside"))

    def test_malformed_node_has_readable_validation_error(self):
        self.check_invalid(lambda raw: raw["nodes"].append(None))


if __name__ == "__main__":
    unittest.main()
