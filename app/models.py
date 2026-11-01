"""UI-independent content and progress contracts."""
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Option:
    id: str
    text: str


@dataclass(frozen=True)
class Question:
    id: str
    kind: str
    prompt: str
    options: tuple[Option, ...]
    answer: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class Node:
    id: str
    name: str
    short_name: str
    time: str
    place: str
    position: tuple[float, float]
    event: str
    spirit: str
    modern: str
    sources: tuple[str, ...]
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class ContentPack:
    id: str
    version: str
    title: str
    scope: str
    review_status: str
    nodes: tuple[Node, ...]


@dataclass
class Attempt:
    first_correct: bool
    mastered: bool
    submissions: int = 1


@dataclass
class Progress:
    pack_id: str
    content_signature: str
    answers: dict[str, Attempt] = field(default_factory=dict)


@dataclass(frozen=True)
class AnswerResult:
    correct: bool
    first_submission: bool
    explanation: str
    node_completed: bool


@dataclass(frozen=True)
class LearningSummary:
    completed_nodes: int
    total_nodes: int
    first_correct: int
    total_questions: int
    mastered_questions: int


class ContentRepository(Protocol):
    def load(self) -> ContentPack: ...


class ProgressStore(Protocol):
    def load(self, pack_id: str, signature: str) -> Progress: ...
    def save(self, progress: Progress) -> None: ...
