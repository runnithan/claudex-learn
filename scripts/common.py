"""Shared helpers for the claudex-learn scripts: repo paths and frontmatter."""

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TOPICS_DIR = REPO_ROOT / "topics"

LEVELS = ("beginner", "intermediate", "advanced")


def slugify(text: str, max_len: int = 80) -> str:
    """Lowercase, hyphen-separated, filename-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def topic_dir(topic: str) -> Path:
    """Resolve a topic name to its directory, exiting with a clear message if missing."""
    path = TOPICS_DIR / topic
    if not path.is_dir():
        existing = sorted(p.name for p in TOPICS_DIR.iterdir() if p.is_dir()) if TOPICS_DIR.is_dir() else []
        print(f"No topic '{topic}' at {path}.", file=sys.stderr)
        if existing:
            print(f"Existing topics: {', '.join(existing)}", file=sys.stderr)
        print("Create one with /new-topic <name>.", file=sys.stderr)
        sys.exit(2)
    return path


def read_frontmatter(path: Path) -> tuple[dict, str]:
    """Split a markdown file into (frontmatter dict, body). No frontmatter gives ({}, text).

    Raises ValueError when a frontmatter block exists but is not a YAML mapping.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"{path}: frontmatter opened with '---' but never closed")
    data = yaml.safe_load(match.group(1)) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: frontmatter is not a key/value mapping")
    return data, match.group(2)


def first_heading(body: str) -> str | None:
    """The text of the first '# ' heading in a markdown body, if any."""
    match = re.search(r"^# (.+)$", body, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def lesson_files(tdir: Path) -> list[Path]:
    """Every lesson file under topics/<topic>/lessons/<category>/ (skips INDEX/README)."""
    lessons = tdir / "lessons"
    if not lessons.is_dir():
        return []
    return sorted(p for p in lessons.glob("*/*.md"))
