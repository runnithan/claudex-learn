---
description: "Quiz yourself on a topic's lessons with spaced repetition: reviews that are due first, then a few new lessons, one question at a time."
argument-hint: "<topic> [number of questions, default 5]"
allowed-tools: Read, Glob, Bash(uv run scripts/srs.py:*)
---

# /quiz: learn it so it sticks

Arguments: `$ARGUMENTS`

**Topic:** the first word names a folder in `topics/`. If it matches none and exactly one topic
exists, use that one. Otherwise list the topics and ask which one. A number in the arguments sets
the session length (default 5).

## Get the session

Run `uv run scripts/srs.py due <topic> --limit <n> --new 3`. It returns `due` (reviews, oldest
first) then `new` (unseen lessons, in learning-path order). If both are empty, say there's nothing
due today, give the `due_today` count and progress from `uv run scripts/srs.py stats <topic>`,
and stop.

## For each lesson, in order

1. Read the lesson file.
2. **Never studied** (anything in `new`, or a `due` item with `reviews: 0`, which `/review`
   flagged before it was learned): teach it first in three to five lines (the TL;DR and How to
   apply, plus the source link), then ask. **A real review:** just ask.
3. Ask **one** question, then stop and wait for the answer. Prefer application over recall: a
   scenario, a "what would you do here", a spot-the-mistake. Base it on the lesson's
   `## Check yourself`, but vary it on later reviews so the learner can't answer from memory of
   the wording. If the question needs a concrete example (a position, a code snippet, a
   sentence), keep it small and make sure it is valid. Prefer examples taken from the lesson or its source.
4. Grade honestly. **Pass** only if the answer gets the core idea right. A partial answer that
   misses the key point, or "I don't know", is a **fail**. Grade only against the lesson, not
   against things it never taught.
5. Give feedback in two to four lines: what they got right, what they missed, and the source link
   (with its timestamp) for a refresher.
6. Record the result **before** the next question, so an abandoned session keeps its progress:
   `uv run scripts/srs.py record <topic> <lesson-id> pass|fail`.

Never reveal the answer before the learner has answered. One question per lesson per session.
If the learner makes a fair case that you graded them wrongly, replace the grade with
`uv run scripts/srs.py record <topic> <lesson-id> pass|fail --amend` (without `--amend` the
wrong grade would stay applied) and say you did.

## End of session

One short block: the score (`4/5`), which lessons to revisit (the fails, with links), how many
lessons are still unseen, and a pointer to `/path <topic>` to see overall progress.
