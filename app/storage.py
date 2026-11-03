"""Atomic JSON persistence. User data never lives in the executable directory."""
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from app.models import Attempt, Progress


class JsonProgressStore:
    def __init__(self, path: Path):
        self.path = path
        self.notice = ""

    def _archive(self, reason: str) -> None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup = self.path.with_name(f"{self.path.stem}.{reason}.{stamp}.json")
        self.path.replace(backup)
        self.notice = f"{reason}，原存档已保留为 {backup.name}，本次从头开始。"

    def load(self, pack_id: str, signature: str) -> Progress:
        fresh = Progress(pack_id, signature)
        if not self.path.exists():
            return fresh
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("schema_version") != 1:
                raise ValueError("存档版本无效")
            if raw.get("pack_id") != pack_id or raw.get("content_signature") != signature:
                self._archive("内容题目已更新")
                return fresh
            if not isinstance(raw.get("answers"), dict):
                raise ValueError("答题记录无效")
            answers = {}
            for qid, item in raw["answers"].items():
                if (not isinstance(item, dict) or type(item.get("first_correct")) is not bool
                        or type(item.get("mastered")) is not bool
                        or type(item.get("submissions")) is not int
                        or item["submissions"] < 1
                        or (item["first_correct"] and not item["mastered"])):
                    raise ValueError("答题记录字段无效")
                answers[qid] = Attempt(item["first_correct"], item["mastered"], item["submissions"])
            learned = raw.get("learned_lessons", {})
            if not isinstance(learned, dict) or any(
                    not isinstance(k, str) or not isinstance(v, str) for k, v in learned.items()):
                raise ValueError("学习完成记录无效")
            return Progress(pack_id, signature, answers, learned)
        except (ValueError, UnicodeError, TypeError):
            self._archive("存档格式异常")
            return fresh

    def save(self, progress: Progress) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        raw = {"schema_version": 1, **asdict(progress)}
        fd, name = tempfile.mkstemp(prefix="progress-", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(raw, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
