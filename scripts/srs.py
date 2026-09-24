#!/usr/bin/env python3
"""Spaced-repetition state for a topic's lessons (a Leitner box scheme).

Usage:
    uv run scripts/srs.py due    <topic> [--limit N] [--new N]   # what to quiz today (JSON)
    uv run scripts/srs.py record <topic> <lesson-id> pass|fail   # log a quiz answer (--amend to regrade)
    uv run scripts/srs.py flag   <topic> <lesson-id>             # make a lesson due today (used by /review)
    uv run scripts/srs.py stats  <topic>                         # progress summary (JSON)

Every command takes --today YYYY-MM-DD to pretend it is another day (used by tests).

State lives in topics/<topic>/progress.json. A lesson moves up one box each time you
pass it and back to box 1 when you fail it; higher boxes come back less often.
A lesson in box 4 or 5 counts as mastered.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

import yaml

from common import LEVELS, first_heading, lesson_files, read_frontmatter, topic_dir

# Days until the next review, by box.
INTERVALS = {1: 1, 2: 3, 3: 7, 4: 16, 5: 35}
MASTERED_BOX = 4


def load_lessons(tdir: Path) -> dict[str, dict]:
    """Active lessons keyed by id: title, category, level, path (relative to the topic dir)."""
    lessons = {}
    for path in lesson_files(tdir):
        try:
            meta, body = read_frontmatter(path)
        except (ValueError, yaml.YAMLError):
            continue  # validate.py reports the broken file; don't take the whole quiz down
        if meta.get("status", "active") != "active" or not meta.get("id"):
            continue
        lessons[meta["id"]] = {
            "id": meta["id"],
            "title": first_heading(body) or meta["id"],
            "category": meta.get("category") or path.parent.name,
            "level": meta.get("level") if meta.get("level") in LEVELS else "intermediate",
            "path": str(path.relative_to(tdir)),
        }
    return lessons


def path_order(tdir: Path, lessons: dict[str, dict]) -> dict[str, int]:
    """Position of each lesson in the learning path (path.md), so new lessons follow it."""
    path_md = tdir / "path.md"
    if not path_md.exists():
        return {}
    text = path_md.read_text(encoding="utf-8")
    order = {}
    for match in re.finditer(r"lessons/[^/\s)]+/([^/\s)]+)\.md", text):
        order.setdefault(match.group(1), len(order))
    return {k: v for k, v in order.items() if k in lessons}


def load_progress(tdir: Path) -> dict:
    path = tdir / "progress.json"
    if not path.exists():
        return {"cards": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("cards", {})
    return data


def save_progress(tdir: Path, data: dict) -> None:
    """Write progress.json atomically so an interrupted write can't corrupt it."""
    fd, tmp = tempfile.mkstemp(dir=tdir, prefix=".progress-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, tdir / "progress.json")


def review(card: dict | None, passed: bool, today: date) -> dict:
    """The card after one quiz answer. A new card starts in box 1."""
    card = dict(card or {"box": 1, "reviews": 0, "lapses": 0})
    if passed:
        card["box"] = min(card.get("box", 1) + 1, max(INTERVALS)) if card.get("reviews") else 2
    else:
        card["box"] = 1
        card["lapses"] = card.get("lapses", 0) + 1
    card["reviews"] = card.get("reviews", 0) + 1
    card["last"] = today.isoformat()
    card["due"] = (today + timedelta(days=INTERVALS[card["box"]])).isoformat()
    return card


def cmd_due(tdir: Path, today: date, limit: int, new_cap: int) -> dict:
    lessons = load_lessons(tdir)
    cards = load_progress(tdir)["cards"]
    order = path_order(tdir, lessons)

    # `reviews: 0` marks a lesson /review flagged before it was ever studied: /quiz teaches it first.
    all_due = [
        {**lessons[i], "box": c.get("box", 1), "due": c.get("due", today.isoformat()), "reviews": c.get("reviews", 0)}
        for i, c in cards.items()
        if i in lessons and c.get("due", today.isoformat()) <= today.isoformat()
    ]
    all_due.sort(key=lambda d: (d["due"], d["box"], d["id"]))
    unseen = [lessons[i] for i in lessons if i not in cards]
    unseen.sort(key=lambda d: (order.get(d["id"], len(order)), LEVELS.index(d["level"]), d["id"]))

    due = all_due[:limit]
    new = unseen[: max(0, min(new_cap, limit - len(due)))]
    return {
        "today": today.isoformat(),
        "due": due,
        "new": new,
        "left_after_session": {"due": len(all_due) - len(due), "unseen": len(unseen) - len(new)},
    }


def cmd_record(tdir: Path, today: date, lesson_id: str, result: str, amend: bool = False) -> dict:
    """Log a quiz answer. With amend, replace the last recorded answer instead of adding one."""
    lessons = load_lessons(tdir)
    if lesson_id not in lessons:
        print(f"No active lesson with id '{lesson_id}' in {tdir.name}.", file=sys.stderr)
        sys.exit(2)
    data = load_progress(tdir)
    current = data["cards"].get(lesson_id)
    if amend:
        if not current or "prev" not in current:
            print(f"Nothing to amend: no recorded answer for '{lesson_id}'.", file=sys.stderr)
            sys.exit(2)
        before = current["prev"]
    else:
        before = {k: v for k, v in current.items() if k != "prev"} if current else None
    card = review(before, result == "pass", today)
    card["prev"] = before
    data["cards"][lesson_id] = card
    save_progress(tdir, data)
    return {"id": lesson_id, "result": result, **{k: v for k, v in card.items() if k != "prev"}}


def cmd_flag(tdir: Path, today: date, lesson_id: str) -> dict:
    lessons = load_lessons(tdir)
    if lesson_id not in lessons:
        print(f"No active lesson with id '{lesson_id}' in {tdir.name}.", file=sys.stderr)
        sys.exit(2)
    data = load_progress(tdir)
    card = dict(data["cards"].get(lesson_id) or {"box": 1, "reviews": 0, "lapses": 0})
    card["due"] = today.isoformat()
    data["cards"][lesson_id] = card
    save_progress(tdir, data)
    return {"id": lesson_id, "flagged": True, **card}


def cmd_stats(tdir: Path, today: date) -> dict:
    lessons = load_lessons(tdir)
    cards = {i: c for i, c in load_progress(tdir)["cards"].items() if i in lessons}
    by_category: dict[str, dict] = {}
    for lesson in lessons.values():
        row = by_category.setdefault(lesson["category"], {"lessons": 0, "seen": 0, "mastered": 0})
        row["lessons"] += 1
        card = cards.get(lesson["id"])
        if card and card.get("reviews"):
            row["seen"] += 1
        if card and card.get("box", 1) >= MASTERED_BOX:
            row["mastered"] += 1
    return {
        "today": today.isoformat(),
        "lessons": len(lessons),
        "seen": sum(1 for c in cards.values() if c.get("reviews")),
        "mastered": sum(1 for c in cards.values() if c.get("box", 1) >= MASTERED_BOX),
        "due_today": sum(1 for c in cards.values() if c.get("due", "") <= today.isoformat()),
        "by_category": dict(sorted(by_category.items())),
        "mastered_ids": sorted(i for i, c in cards.items() if c.get("box", 1) >= MASTERED_BOX),
        "seen_ids": sorted(i for i, c in cards.items() if c.get("reviews")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Spaced-repetition state for a topic.")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_due = sub.add_parser("due")
    p_due.add_argument("topic")
    p_due.add_argument("--limit", type=int, default=5, help="max lessons this session")
    p_due.add_argument("--new", type=int, default=3, help="max unseen lessons to introduce")
    p_rec = sub.add_parser("record")
    p_rec.add_argument("topic")
    p_rec.add_argument("lesson_id")
    p_rec.add_argument("result", choices=["pass", "fail"])
    p_rec.add_argument("--amend", action="store_true", help="replace the last recorded answer (a regrade)")
    p_flag = sub.add_parser("flag")
    p_flag.add_argument("topic")
    p_flag.add_argument("lesson_id")
    p_stats = sub.add_parser("stats")
    p_stats.add_argument("topic")
    for p in (p_due, p_rec, p_flag, p_stats):
        p.add_argument("--today", type=date.fromisoformat, default=argparse.SUPPRESS)
    args = parser.parse_args()

    tdir = topic_dir(args.topic)
    if args.cmd == "due":
        out = cmd_due(tdir, args.today, args.limit, args.new)
    elif args.cmd == "record":
        out = cmd_record(tdir, args.today, args.lesson_id, args.result, args.amend)
    elif args.cmd == "flag":
        out = cmd_flag(tdir, args.today, args.lesson_id)
    else:
        out = cmd_stats(tdir, args.today)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
