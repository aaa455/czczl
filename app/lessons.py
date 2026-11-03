"""Optional lesson sidecar: text/images can change without editing quiz data."""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

from app.content import ContentError, _text
from app.models import ContentPack, LearningScene, Lesson, Node


def placeholder_lesson(node: Node) -> Lesson:
    return Lesson(node.id, (
        LearningScene("background", "历史背景", "【学习文字占位】这里将介绍事件发生的时间、地点与背景。"),
        LearningScene("event", "事件经过", "【学习文字占位】这里将结合配图，讲述本节点的重要史事。"),
        LearningScene("meaning", "理解与思考", "【学习文字占位】这里将梳理事件意义，并联系接下来的知识检验。"),
    ), "【学习小结占位】这里将归纳本段需要掌握的知识。当前版本只演示学习流程。")


def lesson_signature(lesson: Lesson) -> str:
    # Replacing narrative/assets invalidates only the lesson marker, never quiz results.
    return hashlib.sha256(json.dumps(asdict(lesson), ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()


def resolve_image(directory: Path, image: str) -> Path | None:
    if not image:
        return None
    portable = image.replace("\\", "/")
    path = PurePosixPath(portable)
    if path.is_absolute() or PureWindowsPath(image).drive or ".." in path.parts or ":" in portable:
        raise ContentError("分镜图片必须是内容包目录内的相对路径")
    base = directory.resolve()
    candidate = (base / portable).resolve()
    if not candidate.is_relative_to(base):
        raise ContentError("分镜图片不能超出内容包目录")
    return candidate


class JsonLessonRepository:
    def __init__(self, directory: Path):
        self.directory = directory

    def load(self, pack: ContentPack) -> dict[str, Lesson]:
        lessons = {node.id: placeholder_lesson(node) for node in pack.nodes}
        sidecar = self.directory / "lessons.json"
        if not sidecar.exists():
            return lessons
        try:
            raw = json.loads(sidecar.read_text(encoding="utf-8-sig"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                raise ContentError("lessons.json 的 schema_version 必须为1")
            if not isinstance(raw.get("lessons"), list):
                raise ContentError("lessons 必须是数组")
            seen = set()
            for item in raw["lessons"]:
                node_id = _text(item, "node_id")
                if node_id not in lessons or node_id in seen:
                    raise ContentError(f"学习节点不存在或重复：{node_id}")
                seen.add(node_id)
                if not isinstance(item.get("scenes"), list) or not item["scenes"]:
                    raise ContentError(f"{node_id} 至少需要一个分镜")
                scenes, scene_ids = [], set()
                for scene in item["scenes"]:
                    scene_id = _text(scene, "id")
                    if scene_id in scene_ids:
                        raise ContentError(f"{node_id} 分镜编号重复：{scene_id}")
                    scene_ids.add(scene_id)
                    duration = scene.get("duration_ms", 12000)
                    if type(duration) is not int or not 1000 <= duration <= 120000:
                        raise ContentError(f"{node_id}/{scene_id} 时长应为1000—120000毫秒")
                    transition = scene.get("transition", "fade")
                    if transition not in ("fade", "none"):
                        raise ContentError(f"{node_id}/{scene_id} 不支持该转场")
                    image = scene.get("image", "")
                    alt = scene.get("image_alt", "学习配图")
                    if not isinstance(image, str) or not isinstance(alt, str):
                        raise ContentError("分镜image和image_alt必须为文本")
                    resolve_image(self.directory, image)
                    scenes.append(LearningScene(scene_id, _text(scene, "title"),
                                                _text(scene, "text"), image, alt, duration,
                                                transition, _text(scene, "type")))
                lessons[node_id] = Lesson(node_id, tuple(scenes), _text(item, "summary"))
            return lessons
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ContentError(f"学习分镜读取失败：{exc}") from exc
