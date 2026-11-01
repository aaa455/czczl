"""A runs this after changing content. Optional external directory argument."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.content import JsonContentRepository
from app.learning import default_registry


def main() -> int:
    directory = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "assets/content"
    try:
        pack = JsonContentRepository(directory).load()
        registry = default_registry()
        for node in pack.nodes:
            for question in node.questions:
                if not registry.supports(question.kind):
                    raise ValueError(f"尚未注册题型：{question.kind}")
        print(f"PASS: {len(pack.nodes)} nodes, {sum(len(n.questions) for n in pack.nodes)} questions")
        if pack.review_status == "draft":
            print("NOTE: Content is a draft. Historical sources still require team review.")
        return 0
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
