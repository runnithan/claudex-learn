import json

import pytest

import validate
from conftest import write_lesson

TOPIC_MD = """---
name: demo
title: Demo
goal: Learn the demo
level: beginner
categories: [basics]
---

# Demo
"""


@pytest.fixture
def valid_topic(topic, monkeypatch):
    monkeypatch.setattr(validate, "REPO_ROOT", topic.parent.parent)
    (topic / "topic.md").write_text(TOPIC_MD, encoding="utf-8")
    write_lesson(topic, "one")
    (topic / "lessons" / "INDEX.md").write_text("- [One](basics/one.md): hook\n", encoding="utf-8")
    (topic / "lessons" / ".processed.json").write_text(json.dumps({"processed": []}), encoding="utf-8")
    return topic


def run(tdir):
    report = validate.Report()
    validate.check_topic(tdir, report)
    return report


def test_valid_topic_passes(valid_topic):
    report = run(valid_topic)
    assert report.errors == [] and report.warnings == []


def test_unlisted_lesson_and_bad_category_are_errors(valid_topic):
    write_lesson(valid_topic, "two", category="other")
    errors = run(valid_topic).errors
    assert any("`other` is not in topic.md categories" in e for e in errors)
    assert any("active lesson `two` is not listed" in e for e in errors)


def test_superseded_lesson_must_point_forward_and_leave_the_index(valid_topic):
    write_lesson(valid_topic, "one", status="superseded")
    errors = run(valid_topic).errors
    assert any("superseded_by" in e for e in errors)
    assert any("lists `one`, which is not an active lesson" in e for e in errors)


def test_supersession_must_be_recorded_on_both_lessons(valid_topic):
    new = write_lesson(valid_topic, "two")
    new.write_text(new.read_text(encoding="utf-8").replace("supersedes: null", "supersedes: one"), encoding="utf-8")
    (valid_topic / "lessons" / "INDEX.md").write_text(
        "- [One](basics/one.md): a\n- [Two](basics/two.md): b\n", encoding="utf-8"
    )
    assert any("that lesson isn't `status: superseded`" in e for e in run(valid_topic).errors)


def test_duplicate_ids_across_categories_are_errors(valid_topic):
    text = (valid_topic / "topic.md").read_text(encoding="utf-8")
    (valid_topic / "topic.md").write_text(text.replace("[basics]", "[basics, other]"), encoding="utf-8")
    dup = valid_topic / "lessons" / "other" / "one.md"
    dup.parent.mkdir()
    dup.write_text((valid_topic / "lessons" / "basics" / "one.md").read_text(encoding="utf-8").replace(
        "category: basics", "category: other"), encoding="utf-8")
    assert any("ids must be unique" in e for e in run(valid_topic).errors)


def test_lessons_with_empty_categories_are_an_error(valid_topic):
    text = (valid_topic / "topic.md").read_text(encoding="utf-8")
    (valid_topic / "topic.md").write_text(text.replace("[basics]", "[]"), encoding="utf-8")
    assert any("`categories` is empty" in e for e in run(valid_topic).errors)


def test_path_with_superseded_lesson_warns_and_duplicates_error(valid_topic):
    new = write_lesson(valid_topic, "two")
    new.write_text(new.read_text(encoding="utf-8").replace("supersedes: null", "supersedes: one"), encoding="utf-8")
    old = valid_topic / "lessons" / "basics" / "one.md"
    old.write_text(old.read_text(encoding="utf-8").replace("status: active", "status: superseded\nsuperseded_by: two"), encoding="utf-8")
    (valid_topic / "lessons" / "INDEX.md").write_text("- [Two](basics/two.md): b\n", encoding="utf-8")
    (valid_topic / "path.md").write_text("- [One](lessons/basics/one.md)\n- [Two](lessons/basics/two.md)\n", encoding="utf-8")
    report = run(valid_topic)
    assert report.errors == [] and any("no longer active" in w for w in report.warnings)

    (valid_topic / "path.md").write_text("- [Two](lessons/basics/two.md)\n- [Two](lessons/basics/two.md)\n", encoding="utf-8")
    assert any("lists `two` 2 times" in e for e in run(valid_topic).errors)


def test_stale_path_is_a_warning_not_an_error(valid_topic):
    write_lesson(valid_topic, "two")
    (valid_topic / "lessons" / "INDEX.md").write_text(
        "- [One](basics/one.md): a\n- [Two](basics/two.md): b\n", encoding="utf-8"
    )
    (valid_topic / "path.md").write_text("- [One](lessons/basics/one.md)\n", encoding="utf-8")
    report = run(valid_topic)
    assert report.errors == []
    assert any("not in the path yet" in w for w in report.warnings)
