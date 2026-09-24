---
description: "Get feedback on your own work (code, an essay, a chess game, a plan) measured against a topic's lessons, with links back to the sources."
argument-hint: "<topic> <file path | pasted work>"
allowed-tools: Read, Glob, Grep, Write, Bash(uv run scripts/srs.py:*), Bash(ls:*)
---

# /review: how does my work measure up?

Arguments: `$ARGUMENTS`

**Topic:** the first word names a folder in `topics/`. If it matches none and exactly one topic
exists, use that one. Otherwise list the topics and ask which one. The rest is the work: a path to
a file, or the work pasted inline. If there's no work, ask for it and mention what `topic.md`
says practice looks like.

## Result

Feedback in chat, grounded in the lessons, with this shape:

1. **What this is:** one line saying what you're reviewing.
2. **Done well:** up to three things, each tied to a lesson the work shows was applied.
3. **Change next:** up to three changes, the most important first. Each says *where* in the work
   (quote it, or give the line, move number or paragraph), *what* to change, *why* (the lesson,
   linked as `topics/<topic>/lessons/<category>/<id>.md`), and the source link with its timestamp.
4. **Not covered:** anything notable the lessons don't speak to. You may add general advice
   here, but label it clearly as not coming from the library.
5. **Drill:** the lessons behind "Change next", now queued for the next `/quiz`.

Then:

- Save the same feedback to `topics/<topic>/reviews/<YYYY-MM-DD>-<slug>.md`, starting with a
  line saying what was reviewed (the file path, or the pasted work in a fenced block), so the
  learner can see progress across reviews.
- For each lesson in "Change next", run `uv run scripts/srs.py flag <topic> <lesson-id>` so it
  comes up in the next quiz.

## How to judge

- Read `topic.md` first, especially `## Practice and review`: it says what this learner's work
  looks like and what to focus on. Then read `lessons/INDEX.md` and every lesson relevant to the
  work, in full. In a large library, find them with Grep.
- **Never edit the learner's work.** This command only reads it.
- **Don't fake precision.** If checking something properly needs a tool you don't have (a chess
  engine, a compiler, a native speaker, a measurement), say so and suggest the tool rather than
  guessing. A confident wrong correction does more damage than no correction.
- **Don't invent problems.** If the work applies the lessons well, say so and keep "Change next"
  short or empty. The learner is here to improve, which requires feedback they can trust.
