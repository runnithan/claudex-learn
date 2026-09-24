---
description: "Build or refresh a topic's learning path (stages from beginner to advanced) and show where you are on it."
argument-hint: "<topic> [--rebuild]"
allowed-tools: Read, Write, Edit, Glob, Bash(uv run scripts/srs.py:*), Bash(uv run scripts/validate.py:*)
---

# /path: what to learn next, in order

Arguments: `$ARGUMENTS`

**Topic:** the first word names a folder in `topics/`. If it matches none and exactly one topic
exists, use that one. Otherwise list the topics and ask which one.

## Result

`topics/<topic>/path.md` contains **every active lesson exactly once** (from
`lessons/INDEX.md`), arranged into 3 to 6 stages:

- Each stage builds on the ones before it. Foundations come first, and a lesson never sits
  before a lesson it depends on.
- Each stage has a name, one line on why it comes at that point, and a milestone saying what the
  learner can do after it.
- The path is shaped by the goal and level in `topic.md`. For an intermediate learner, the first
  stage can be a quick "check the basics" pass, but every lesson still appears.

If `path.md` already exists, **refresh it** rather than starting over: keep the stage names and
order, put each superseding lesson where the lesson it replaced was, and slot new lessons into
the stage where they belong. Rebuild from scratch only when the arguments include `--rebuild`, or
when the existing path covers less than half of the active lessons.

Format:

```markdown
# <Topic title>: learning path

Goal: <goal from topic.md>
Built <YYYY-MM-DD> from <N> lessons. Run /path <topic> again after new lessons land.

## Stage 1: <name>

<Why this comes first, in one line.> **Milestone:** <what you can do after this stage>.

- [<Lesson title>](lessons/<category>/<id>.md)
```

`uv run scripts/validate.py <topic>` must report no errors, and no "not in the path" warning.

## Then show where the learner is

Run `uv run scripts/srs.py stats <topic>`. A lesson is **seen** once it has been quizzed and
**mastered** once it reaches box 4 (the `seen_ids` and `mastered_ids` lists). In chat, compactly:

- one line per stage: `Stage 2: Tactics, 3/7 mastered, 5/7 seen`, marking the current stage
  (the first one that isn't fully mastered);
- the next three lessons to learn: unseen lessons in path order, starting in the current stage;
- how many reviews are due today, and a nudge: `/quiz <topic>`.

Don't paste `path.md` itself into the chat; the learner can open it.
