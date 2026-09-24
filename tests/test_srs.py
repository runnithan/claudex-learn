from datetime import date

import pytest

import srs
from conftest import write_lesson

TODAY = date(2026, 3, 1)


def test_new_card_pass_goes_to_box_2_and_fail_to_box_1():
    passed = srs.review(None, True, TODAY)
    failed = srs.review(None, False, TODAY)
    assert (passed["box"], passed["due"]) == (2, "2026-03-04")
    assert (failed["box"], failed["due"], failed["lapses"]) == (1, "2026-03-02", 1)


def test_passes_climb_boxes_and_cap_at_5():
    card = None
    boxes = []
    for _ in range(6):
        card = srs.review(card, True, TODAY)
        boxes.append(card["box"])
    assert boxes == [2, 3, 4, 5, 5, 5]
    assert card["due"] == "2026-04-05"  # box 5 = 35 days


def test_fail_resets_to_box_1():
    card = {"box": 4, "reviews": 3, "lapses": 0}
    card = srs.review(card, False, TODAY)
    assert card["box"] == 1 and card["lapses"] == 1


def test_due_serves_due_cards_then_new_in_path_order(topic):
    for lid, level in [("a-advanced", "advanced"), ("b-basic", "beginner"), ("c-basic", "beginner"), ("d-old", "beginner")]:
        write_lesson(topic, lid, level=level)
    (topic / "path.md").write_text(
        "## Stage 1\n- [C](lessons/basics/c-basic.md)\n- [A](lessons/basics/a-advanced.md)\n", encoding="utf-8"
    )
    srs.save_progress(topic, {"cards": {"d-old": {"box": 2, "reviews": 1, "lapses": 0, "due": "2026-02-28"}}})

    out = srs.cmd_due(topic, TODAY, limit=3, new_cap=5)
    assert [d["id"] for d in out["due"]] == ["d-old"]
    # Path order first (c, then a), then lessons not in the path by level.
    assert [n["id"] for n in out["new"]] == ["c-basic", "a-advanced"]
    assert out["left_after_session"] == {"due": 0, "unseen": 1}


def test_due_ignores_superseded_lessons(topic):
    write_lesson(topic, "old", status="superseded")
    write_lesson(topic, "new")
    out = srs.cmd_due(topic, TODAY, limit=5, new_cap=5)
    assert [n["id"] for n in out["new"]] == ["new"]


def test_record_and_stats_round_trip(topic):
    for lid in ("x", "y"):
        write_lesson(topic, lid)
    srs.cmd_record(topic, TODAY, "x", "pass")
    for _ in range(3):
        srs.cmd_record(topic, TODAY, "x", "pass")
    srs.cmd_record(topic, TODAY, "y", "fail")
    stats = srs.cmd_stats(topic, date(2026, 3, 2))
    assert stats["lessons"] == 2 and stats["seen"] == 2
    assert stats["mastered_ids"] == ["x"]
    assert stats["due_today"] == 1  # y failed yesterday, due today
    assert stats["by_category"]["basics"] == {"lessons": 2, "seen": 2, "mastered": 1}


def test_flag_makes_a_lesson_due_today(topic):
    write_lesson(topic, "x")
    srs.cmd_record(topic, TODAY, "x", "pass")
    srs.cmd_flag(topic, date(2026, 3, 2), "x")
    out = srs.cmd_due(topic, date(2026, 3, 2), limit=5, new_cap=0)
    assert [(d["id"], d["reviews"]) for d in out["due"]] == [("x", 1)]


def test_flagging_an_unstudied_lesson_shows_zero_reviews(topic):
    write_lesson(topic, "x")
    srs.cmd_flag(topic, TODAY, "x")
    out = srs.cmd_due(topic, TODAY, limit=5, new_cap=5)
    assert [(d["id"], d["reviews"]) for d in out["due"]] == [("x", 0)] and out["new"] == []


def test_amend_replaces_the_last_grade_instead_of_stacking(topic):
    write_lesson(topic, "x")
    for _ in range(3):
        srs.cmd_record(topic, TODAY, "x", "pass")  # box 4
    srs.cmd_record(topic, TODAY, "x", "fail")
    amended = srs.cmd_record(topic, TODAY, "x", "pass", amend=True)
    assert (amended["box"], amended["reviews"], amended["lapses"]) == (5, 4, 0)
    again = srs.cmd_record(topic, TODAY, "x", "pass", amend=True)  # amending twice is stable
    assert (again["box"], again["reviews"]) == (5, 4)


def test_amend_without_a_prior_answer_exits(topic):
    write_lesson(topic, "x")
    with pytest.raises(SystemExit):
        srs.cmd_record(topic, TODAY, "x", "pass", amend=True)


def test_a_malformed_lesson_does_not_break_the_quiz(topic):
    write_lesson(topic, "good")
    bad = topic / "lessons" / "basics" / "bad.md"
    bad.write_text("---\nid: bad\nsources:\n  - title: Chess: the basics\n---\n# Bad\n", encoding="utf-8")
    out = srs.cmd_due(topic, TODAY, limit=5, new_cap=5)
    assert [n["id"] for n in out["new"]] == ["good"]
