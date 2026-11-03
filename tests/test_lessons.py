from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.content import ContentError, JsonContentRepository
from app.learning import LearningService
from app.lessons import JsonLessonRepository, lesson_signature, placeholder_lesson, resolve_image
from app.storage import JsonProgressStore

CONTENT = Path(__file__).resolve().parents[1] / "assets/content"


class LessonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.store = JsonProgressStore(self.directory / "progress.json")
        self.pack = JsonContentRepository(CONTENT).load()
        self.lessons = JsonLessonRepository(CONTENT).load(self.pack)
        self.service = LearningService(self.pack, self.store, lessons=self.lessons)

    def test_must_learn_before_quiz_and_marker_survives_restart(self):
        node = self.pack.nodes[0]
        q = node.questions[0]
        with self.assertRaisesRegex(ValueError, "本段学习"):
            self.service.submit(node.id, q.id, q.answer)
        self.service.complete_lesson(node.id)
        reloaded = LearningService(self.pack, self.store, lessons=self.lessons)
        self.assertTrue(reloaded.lesson_learned(node.id))
        self.assertTrue(reloaded.submit(node.id, q.id, q.answer).correct)

    def test_locked_lesson_and_write_failure_cannot_mark_learned(self):
        with self.assertRaisesRegex(ValueError, "前面"):
            self.service.complete_lesson(self.pack.nodes[1].id)
        with patch.object(self.store, "save", side_effect=OSError("read only")):
            with self.assertRaises(OSError):
                self.service.complete_lesson(self.pack.nodes[0].id)
        self.assertEqual(self.service.progress.learned_lessons, {})

    def test_lesson_edit_relearns_without_erasing_partial_quiz_results(self):
        node = self.pack.nodes[0]
        self.service.complete_lesson(node.id)
        self.service.submit(node.id, node.questions[0].id, node.questions[0].answer)
        lesson = self.lessons[node.id]
        changed = dict(self.lessons)
        changed[node.id] = replace(lesson, scenes=(replace(lesson.scenes[0], text="正式学习内容"),
                                                  *lesson.scenes[1:]))
        reloaded = LearningService(self.pack, self.store, lessons=changed)
        self.assertFalse(reloaded.lesson_learned(node.id))
        self.assertFalse(reloaded.can_quiz(node.id))
        self.assertEqual(reloaded.summary().first_correct, 1)
        self.assertEqual(len(reloaded.progress.answers), 1)

    def test_legacy_save_keeps_quiz_results_and_allows_completed_review(self):
        node = self.pack.nodes[0]
        self.service.complete_lesson(node.id)
        for q in node.questions:
            self.service.submit(node.id, q.id, q.answer)
        raw = json.loads(self.store.path.read_text(encoding="utf-8"))
        del raw["learned_lessons"]
        self.store.path.write_text(json.dumps(raw), encoding="utf-8")
        reloaded = LearningService(self.pack, self.store, lessons=self.lessons)
        self.assertFalse(reloaded.lesson_learned(node.id))
        self.assertTrue(reloaded.can_quiz(node.id))
        self.assertEqual(reloaded.summary().first_correct, len(node.questions))
        reloaded.reset()
        self.assertEqual(reloaded.progress.learned_lessons, {})

    def test_old_content_pack_without_sidecar_gets_placeholders(self):
        lessons = JsonLessonRepository(self.directory).load(self.pack)
        self.assertEqual(len(lessons), len(self.pack.nodes))
        self.assertTrue(all(len(lesson.scenes) == 3 for lesson in lessons.values()))
        self.assertTrue(all(not scene.image for lesson in lessons.values() for scene in lesson.scenes))

    def test_new_image_text_and_variable_scene_count(self):
        raw = {"schema_version": 1, "lessons": [{"node_id": self.pack.nodes[0].id,
            "summary": "学习小结", "scenes": [{"id": "only", "type": "image_text", "title": "标题",
            "text": "正文", "image": "images/test.png", "duration_ms": 5000, "transition": "none"}]}]}
        (self.directory / "lessons.json").write_text(json.dumps(raw), encoding="utf-8")
        lessons = JsonLessonRepository(self.directory).load(self.pack)
        lesson = lessons[self.pack.nodes[0].id]
        self.assertEqual(len(lesson.scenes), 1)
        self.assertEqual(lesson.scenes[0].image, "images/test.png")
        self.assertEqual(lesson.scenes[0].text, "正文")
        self.assertNotEqual(lesson_signature(lesson), lesson_signature(placeholder_lesson(self.pack.nodes[0])))

    def test_invalid_sidecars_have_readable_errors(self):
        source = json.loads((CONTENT / "lessons.json").read_text(encoding="utf-8"))
        edits = [lambda r: r.update(schema_version=99),
                 lambda r: r["lessons"][0].update(node_id="not-a-node"),
                 lambda r: r["lessons"].append(r["lessons"][0]),
                 lambda r: r["lessons"][0].update(scenes=[]),
                 lambda r: r["lessons"][0]["scenes"].append(r["lessons"][0]["scenes"][0]),
                 lambda r: r["lessons"][0]["scenes"][0].update(duration_ms=True),
                 lambda r: r["lessons"][0]["scenes"][0].update(duration_ms=0),
                 lambda r: r["lessons"][0]["scenes"][0].update(image="../outside.png"),
                 lambda r: r["lessons"][0]["scenes"][0].update(transition="unknown"),
                 lambda r: r["lessons"][0]["scenes"].append(None)]
        for edit in edits:
            with self.subTest(edit=edit):
                raw = json.loads(json.dumps(source))
                edit(raw)
                (self.directory / "lessons.json").write_text(json.dumps(raw), encoding="utf-8")
                with self.assertRaises(ContentError):
                    JsonLessonRepository(self.directory).load(self.pack)

    def test_image_paths_stay_inside_content_directory(self):
        for path in ["../a.png", "..\\a.png", "C:/a.png", "/a.png", "//server/share/a.png"]:
            with self.subTest(path=path), self.assertRaises(ContentError):
                resolve_image(self.directory, path)
        self.assertEqual(resolve_image(self.directory, "images/test.png"),
                         (self.directory / "images/test.png").resolve())


if __name__ == "__main__":
    unittest.main()
