---
description: "Start learning a new topic: records your goal, starting level and what your practice looks like, and creates the topic's folder."
argument-hint: "<topic name> [anything you already want to say about your goal]"
allowed-tools: Read, Write, Glob, Bash(uv run scripts/validate.py:*)
---

# /new-topic: set up a topic to learn

Arguments: `$ARGUMENTS`

## Result

A new folder `topics/<slug>/` holding `topic.md` and `sources/urls.txt`, and a learner who knows
what to do next. `<slug>` is the topic name in kebab-case (`Music theory` → `music-theory`).

If `topics/<slug>/` already exists, stop and say so; never overwrite a topic.

## What to ask

Ask everything in **one** short message, skipping anything the arguments already answer:

1. What do you want to be able to do? Push for something concrete ("read a balance sheet",
   "beat my friend at chess", "hold a 10-minute conversation in Spanish").
2. Where are you starting from? Beginner, intermediate or advanced, plus what you already know.
3. What will your practice look like? This is what you'll hand to `/review`: code, an essay, a
   game record, a plan, a log of workouts, notes on a recording.
4. Any creators, channels or sites you already trust? (Optional.)

## topic.md

```markdown
---
name: <slug>
title: <Readable title>
goal: <one sentence: what the learner wants to be able to do>
level: beginner            # beginner | intermediate | advanced
created: <YYYY-MM-DD>
categories: []             # filled in by the first /extract-lessons run
practice: <one line: what the learner will hand to /review>
---

# <Title>

## Goal

<The goal in the learner's words, and why it matters to them.>

## Starting point

<What they already know and where they get stuck.>

## Practice and review

<What practice work looks like and what /review should pay attention to, including limits
such as "no chess engine available, so judge plans and principles rather than exact moves".>

## Trusted sources

<Creators or sites the learner named. Leave "None yet" if they gave none; never invent any.>
```

`sources/urls.txt` starts with these comment lines and no URLs:

```text
# One URL per line: YouTube videos or web articles.
# Lines starting with # are ignored. Run /add-source or
# `uv run scripts/fetch_sources.py <topic>` to fetch them.
```

## Done when

- `uv run scripts/validate.py <slug>` reports no errors.
- You've told the learner the next step in two or three lines: add material with
  `/add-source <slug> <url, file or pasted text>` (or drop `.md` files into
  `topics/<slug>/sources/` and URLs into `urls.txt`), then run `/extract-lessons <slug>`.
