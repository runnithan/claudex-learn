#!/usr/bin/env python3
"""Check that commands, topics and lesson libraries are well-formed.

Usage:
    uv run scripts/validate.py            # every topic
    uv run scripts/validate.py chess      # one topic

Exits 1 on any error. Warnings (a learning path missing new lessons, say) don't fail.
The commands run this as their self-check, and so does CI.
"""

import json
import re
import sys
from pathlib import Path

import yaml

from common import LEVELS, REPO_ROOT, TOPICS_DIR, lesson_files, read_frontmatter

COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


class Report:
    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, where: Path, msg: str) -> None:
        self.errors.append(f"{where.relative_to(REPO_ROOT)}: {msg}")

    def warn(self, where: Path, msg: str) -> None:
        self.warnings.append(f"{where.relative_to(REPO_ROOT)}: {msg}")


def frontmatter(path: Path, report: Report) -> tuple[dict, str] | None:
    try:
        return read_frontmatter(path)
    except (ValueError, yaml.YAMLError) as e:
        report.error(path, f"bad frontmatter ({str(e).splitlines()[0]})")
        return None


def check_commands(report: Report) -> int:
    count = 0
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        count += 1
        parsed = frontmatter(path, report)
        if parsed is None:
            continue
        meta, body = parsed
        if not meta.get("description"):
            report.error(path, "missing `description` in frontmatter")
        if "$ARGUMENTS" not in body and meta.get("argument-hint"):
            report.warn(path, "has an argument-hint but never reads $ARGUMENTS")
    return count


def check_lesson(path: Path, meta: dict, body: str, categories: list, report: Report) -> None:
    if meta.get("id") != path.stem:
        report.error(path, f"id `{meta.get('id')}` does not match the filename")
    if meta.get("status") not in ("active", "superseded"):
        report.error(path, "status must be `active` or `superseded`")
    if meta.get("category") != path.parent.name:
        report.error(path, f"category `{meta.get('category')}` does not match its folder `{path.parent.name}`")
    elif categories and meta["category"] not in categories:
        report.error(path, f"category `{meta['category']}` is not in topic.md categories")
    if meta.get("level") not in LEVELS:
        report.error(path, f"level must be one of {', '.join(LEVELS)}")
    sources = meta.get("sources")
    if not isinstance(sources, list) or not sources:
        report.error(path, "needs a non-empty `sources` list")
    else:
        for src in sources:
            if not isinstance(src, dict) or not (src.get("url") or src.get("file")):
                report.error(path, "each source needs a `url` or a `file`")
                break
    if not re.search(r"^# .+", body, flags=re.MULTILINE):
        report.error(path, "missing a `# Title` heading")
    if "## TL;DR" not in body:
        report.error(path, "missing a `## TL;DR` section")


def check_topic(tdir: Path, report: Report) -> int:
    topic_md = tdir / "topic.md"
    if not topic_md.exists():
        report.error(tdir, "missing topic.md (create topics with /new-topic)")
        return 0
    parsed = frontmatter(topic_md, report)
    categories: list = []
    if parsed:
        meta, _ = parsed
        if meta.get("name") != tdir.name:
            report.error(topic_md, f"name `{meta.get('name')}` does not match the folder `{tdir.name}`")
        for key in ("title", "goal"):
            if not meta.get(key):
                report.error(topic_md, f"missing `{key}`")
        if meta.get("level") not in LEVELS:
            report.error(topic_md, f"level must be one of {', '.join(LEVELS)}")
        categories = meta.get("categories") or []
        if not isinstance(categories, list):
            report.error(topic_md, "`categories` must be a list")
            categories = []

    lessons: dict[str, dict] = {}
    for path in lesson_files(tdir):
        parsed = frontmatter(path, report)
        if parsed is None:
            continue
        meta, body = parsed
        check_lesson(path, meta, body, categories, report)
        if meta.get("id") in lessons:
            other = lessons[meta["id"]]["path"].relative_to(tdir)
            report.error(path, f"id `{meta['id']}` is also used by {other}; ids must be unique across categories")
        elif meta.get("id"):
            lessons[meta["id"]] = {"meta": meta, "path": path}

    if lessons and not categories:
        report.error(topic_md, "has lessons but `categories` is empty; list the categories in use")

    for lid, info in lessons.items():
        meta, path = info["meta"], info["path"]
        if meta.get("status") == "superseded" and meta.get("superseded_by") not in lessons:
            report.error(path, "superseded lessons need `superseded_by` naming an existing lesson")
        old_id = meta.get("supersedes")
        if old_id:
            old = lessons.get(old_id)
            if old is None:
                report.error(path, f"supersedes `{old_id}`, which does not exist")
            elif old["meta"].get("status") != "superseded" or old["meta"].get("superseded_by") != lid:
                report.error(path, f"supersedes `{old_id}`, but that lesson isn't `status: superseded` with `superseded_by: {lid}`")

    active = {lid for lid, info in lessons.items() if info["meta"].get("status") == "active"}
    lessons_dir = tdir / "lessons"
    index = lessons_dir / "INDEX.md"
    if lessons and not index.exists():
        report.error(lessons_dir, "has lessons but no INDEX.md")
    elif index.exists():
        linked = re.findall(r"\]\(([^)\s]+\.md)\)", index.read_text(encoding="utf-8"))
        seen: dict[str, int] = {}
        for link in linked:
            target = lessons_dir / link
            if not target.exists():
                report.error(index, f"links to missing file `{link}`")
                continue
            seen[target.stem] = seen.get(target.stem, 0) + 1
        for lid in sorted(active):
            if lid not in seen:
                report.error(index, f"active lesson `{lid}` is not listed")
            elif seen[lid] > 1:
                report.error(index, f"lesson `{lid}` is listed {seen[lid]} times")
        for lid in sorted(set(seen) - active):
            report.error(index, f"lists `{lid}`, which is not an active lesson")

    ledger = lessons_dir / ".processed.json"
    if ledger.exists():
        try:
            data = json.loads(ledger.read_text(encoding="utf-8"))
            if not isinstance(data.get("processed"), list):
                report.error(ledger, "needs a `processed` list")
        except (json.JSONDecodeError, AttributeError):
            report.error(ledger, "is not valid JSON of the form {\"processed\": [...]}")
    elif lessons:
        report.error(lessons_dir, "has lessons but no .processed.json ledger")

    path_md = tdir / "path.md"
    if path_md.exists():
        in_path = re.findall(r"\((lessons/[^)\s]+\.md)\)", path_md.read_text(encoding="utf-8"))
        path_ids: dict[str, int] = {}
        for link in in_path:
            target = tdir / link
            if not target.exists():
                report.error(path_md, f"links to missing file `{link}`")
            elif target.stem not in active:
                # New lessons can supersede old ones before /path runs again: stale, not broken.
                report.warn(path_md, f"includes `{target.stem}`, which is no longer active; run /path to refresh")
            path_ids[target.stem] = path_ids.get(target.stem, 0) + 1
        for lid, n in sorted(path_ids.items()):
            if n > 1:
                report.error(path_md, f"lists `{lid}` {n} times; each lesson belongs to one stage")
        missing = sorted(active - set(path_ids))
        if missing:
            report.warn(path_md, f"{len(missing)} active lesson(s) not in the path yet; run /path to refresh")

    progress = tdir / "progress.json"
    if progress.exists():
        try:
            json.loads(progress.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report.error(progress, "is not valid JSON")
    return len(lessons)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    report = Report()
    commands = check_commands(report)
    if len(sys.argv) > 1:
        topics = [TOPICS_DIR / name for name in sys.argv[1:]]
        for t in topics:
            if not t.is_dir():
                print(f"No topic folder {t}", file=sys.stderr)
                return 2
    else:
        topics = sorted(p for p in TOPICS_DIR.iterdir() if p.is_dir()) if TOPICS_DIR.is_dir() else []
    lesson_count = sum(check_topic(t, report) for t in topics)

    for w in report.warnings:
        print(f"WARN  {w}")
    for e in report.errors:
        print(f"ERROR {e}")
    status = "FAIL" if report.errors else "OK"
    print(
        f"{status}: {commands} command(s), {len(topics)} topic(s), {lesson_count} lesson(s), "
        f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
