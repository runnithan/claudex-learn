import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

LESSON = """---
id: {id}
created: 2026-01-01
status: {status}
supersedes: null
category: {category}
level: {level}
sources:
  - url: https://example.com/article
    title: Example
---

# {title}

## TL;DR

Something worth knowing.
"""


@pytest.fixture
def topic(tmp_path, monkeypatch):
    """A throwaway topics/<name>/ tree, with the scripts pointed at it."""
    import common

    topics = tmp_path / "topics"
    tdir = topics / "demo"
    (tdir / "lessons").mkdir(parents=True)
    monkeypatch.setattr(common, "TOPICS_DIR", topics)
    monkeypatch.setattr(common, "REPO_ROOT", tmp_path)
    return tdir


def write_lesson(tdir: Path, lesson_id: str, category="basics", level="beginner", status="active", title=None):
    path = tdir / "lessons" / category / f"{lesson_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        LESSON.format(id=lesson_id, status=status, category=category, level=level, title=title or lesson_id),
        encoding="utf-8",
    )
    return path
