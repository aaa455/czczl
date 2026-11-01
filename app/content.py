"""Strict JSON content loading; adding a node requires no UI changes."""
import json
import math
from pathlib import Path
import re

from app.models import ContentPack, Node, Option, Question


class ContentError(ValueError):
    pass


def _text(item: dict, key: str) -> str:
    if not isinstance(item, dict):
        raise ContentError(f"字段 {key} 所在条目必须是对象")
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContentError(f"字段 {key} 必须是非空文本")
    return value


class JsonContentRepository:
    def __init__(self, directory: Path):
        self.directory = directory

    def load(self) -> ContentPack:
        try:
            raw = json.loads((self.directory / "nodes.json").read_text(encoding="utf-8-sig"))
            return self._parse(raw)
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise ContentError(f"内容包读取失败：{exc}") from exc

    def _parse(self, raw: dict) -> ContentPack:
        if not isinstance(raw, dict) or raw.get("schema_version") != 1:
            raise ContentError("内容包 schema_version 必须为 1")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", _text(raw, "id")):
            raise ContentError("内容包id仅允许英文、数字、下划线和连字符，最长64位")
        if raw.get("review_status") not in ("draft", "reviewed"):
            raise ContentError("review_status 必须为 draft 或 reviewed")
        if not isinstance(raw.get("nodes"), list) or not raw["nodes"]:
            raise ContentError("至少需要一个学习节点")
        node_ids: set[str] = set()
        question_ids: set[str] = set()
        nodes = []
        for data in raw["nodes"]:
            node_id = _text(data, "id")
            if node_id in node_ids:
                raise ContentError(f"节点编号重复：{node_id}")
            node_ids.add(node_id)
            pos = data.get("position")
            if (not isinstance(pos, list) or len(pos) != 2
                    or any(type(v) not in (int, float) or not math.isfinite(v)
                           or not 0 <= v <= 1 for v in pos)):
                raise ContentError(f"{node_id} 的 position 需要两个 0—1 的坐标")
            sources = data.get("sources")
            if not isinstance(sources, list) or not sources or any(
                    not isinstance(s, str) or not s.strip() for s in sources):
                raise ContentError(f"{node_id} 缺少资料来源")
            questions = []
            if not isinstance(data.get("questions"), list) or not data["questions"]:
                raise ContentError(f"{node_id} 至少需要一道题")
            for q in data["questions"]:
                qid = _text(q, "id")
                if qid in question_ids:
                    raise ContentError(f"题目编号重复：{qid}")
                question_ids.add(qid)
                opts = q.get("options")
                if not isinstance(opts, list) or len(opts) < 2:
                    raise ContentError(f"{qid} 至少需要两个选项")
                options = tuple(Option(_text(o, "id"), _text(o, "text")) for o in opts)
                option_ids = {o.id for o in options}
                if len(option_ids) != len(options):
                    raise ContentError(f"{qid} 的选项编号重复")
                answer = q.get("answer")
                if (not isinstance(answer, list) or not answer
                        or any(not isinstance(a, str) for a in answer)
                        or len(set(answer)) != len(answer)
                        or not set(answer) <= option_ids):
                    raise ContentError(f"{qid} 的 answer 必须引用有效且不重复的选项编号")
                kind = _text(q, "type")
                if kind == "single_choice" and len(answer) != 1:
                    raise ContentError(f"{qid} 单选题只能有一个答案")
                questions.append(Question(qid, kind, _text(q, "prompt"), options,
                                          tuple(answer), _text(q, "explanation")))
            nodes.append(Node(node_id, _text(data, "name"), _text(data, "short_name"),
                              _text(data, "time"), _text(data, "place"), tuple(pos),
                              _text(data, "event"), _text(data, "spirit"),
                              _text(data, "modern"), tuple(sources), tuple(questions)))
        return ContentPack(_text(raw, "id"), _text(raw, "version"), _text(raw, "title"),
                           _text(raw, "scope"), _text(raw, "review_status"), tuple(nodes))
