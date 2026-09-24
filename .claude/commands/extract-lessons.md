---
description: "Mine a topic's sources into short lesson files, one idea each, cited to the exact source (and video timestamp), with newer advice superseding older."
argument-hint: "<topic> [new | all | sources/<file>.md]"
allowed-tools: Read, Write, Edit, Glob, Grep, Agent, Bash(uv run scripts/fetch_sources.py:*), Bash(uv run scripts/validate.py:*), Bash(ls:*), Bash(wc:*)
---

# /extract-lessons: turn sources into lessons

Arguments: `$ARGUMENTS`

**Topic:** the first word names a folder in `topics/`. If it matches none and exactly one topic
exists, use that one. Otherwise list the topics and ask which one. The rest of the arguments:

- empty or `new` (default): mine sources not yet listed in `lessons/.processed.json`;
- `all`: re-mine every source (only worth it after changing what counts as a lesson);
- `sources/<file>.md`: mine just that one source.

All paths below are relative to `topics/<topic>/`.

## What a lesson is

One idea the learner can act on or check their own work against: a principle, a technique, a
common mistake and its fix, a rule of thumb along with its exception, a mental model, a
step-by-step method. Pitch it at the learner's goal and level from `topic.md`.

Not lessons: intros and outros, sponsor reads, pure motivation, anecdotes with no takeaway,
restating the video's title, and trivia that doesn't change what the learner does.

## Result

- Every source in scope has been mined and its path (`sources/<file>.md`) is in
  `lessons/.processed.json` (`{"processed": [...]}`), including sources that yielded nothing.
- New lessons exist as `lessons/<category>/<id>.md` in the format below.
- `lessons/INDEX.md` lists every active lesson exactly once, grouped by category, beginner
  lessons first within each category, and ends with a dated line for this run.
- `topic.md` lists the categories in use under `categories:`.
- `uv run scripts/validate.py <topic>` reports no errors.

Before mining, run `uv run scripts/fetch_sources.py <topic>` so any URLs still pending in
`sources/urls.txt` get fetched (it skips what's already on disk). Report failures and carry on
with the sources that are there. If nothing is left to mine, say so and stop.

## Categories

On the first run, `categories:` in `topic.md` is empty. Choose 3 to 8 kebab-case categories
that fit how this topic is really organised, based on what the sources teach (chess might get
`openings`, `tactics`, `endgames`, `strategy`, `thinking-process`), and write them into `topic.md`.
On later runs, reuse them. Add a category only when at least three new lessons fit none of the
existing ones. Never rename one: its lessons would have to move.

## Mining (sources stay out of this session's context)

Sources are long, so subagents read them in full. Batch roughly 25k words per subagent (the
`words:` field in each source's frontmatter, or `wc -w`), and run at most 4 at a time. Use the
general-purpose agent type, not Explore: Explore reads excerpts, and a miner has to read every word.

Give each miner its source paths, the topic's goal and level, the categories, every existing
lesson id with its INDEX hook, and these rules:

- **One idea per lesson.** Split compound advice: a video listing ten principles is ten lessons.
- **Grounded.** A lesson says only what its sources say. In transcripts, find the `[m:ss]`
  marker nearest the idea and return it as `at`, so the citation can jump to the moment.
- **Sources can be wrong.** If you have good reason to think a claim is wrong, outdated or
  contested, keep the lesson with a `caveat` explaining why, or drop it. Never silently correct it.
- **Level** is relative to this topic: beginner, intermediate or advanced.
- **`check`** is one question that tests whether the learner can *apply* the idea (a scenario,
  a "what would you do"), answerable from the lesson. `/quiz` builds on it. No answer included.
- **Do not write any files.** Return one JSON object:

```json
{
  "candidates": [
    {"id": "kebab-case-claim", "title": "Imperative, specific title", "tldr": "...",
     "why": "...", "how": "...", "check": "...", "caveat": null,
     "category": "one-of-the-categories", "level": "beginner",
     "sources": [{"file": "sources/x.md", "title": "Source title", "url": "https://...", "at": "4:32"}]}
  ],
  "duplicates_of_existing": [{"candidate_id": "...", "existing_id": "...", "note": "same idea"}],
  "contradicts_existing": [{"candidate_id": "...", "existing_id": "...", "reason": "..."}],
  "processed": ["sources/x.md"]
}
```

## Judging the candidates (in this session)

- **Same idea as an active lesson:** don't write a new file. Add the new source to the existing
  lesson's `sources:` list, since corroboration from a second source is worth keeping.
- **Better or corrected advice on the same point:** write the new lesson with
  `supersedes: <old-id>`, and set the old one to `status: superseded` with
  `superseded_by: <new-id>`. Don't delete it. If `path.md` exists, swap the old lesson's link
  there for the new one, so the path stays in step.
- **The same new idea from several sources:** merge into one lesson that cites all of them.
- For a video source, turn `at` into the URL's timestamp: `watch?v=<id>&t=<seconds>s`.

## Lesson format

```markdown
---
id: <same as the filename, kebab-case>
created: <YYYY-MM-DD>
status: active
supersedes: null
category: <one of topic.md's categories, same as the folder>
level: beginner              # beginner | intermediate | advanced
sources:
  - title: "<source title, always quoted: titles often contain colons>"
    url: <url, with &t=<seconds>s for a video moment; omit for pasted text without a URL>
    file: sources/<file>.md
---

# <Imperative, specific title>

## TL;DR

<One or two sentences the learner can act on.>

## Why it matters

<What goes wrong without it, grounded in what the source showed.>

## How to apply

<Concrete steps or an example, plus the exception to the rule if the source gives one.>

## Check yourself

<One application question. No answer.>

## Caveat

<Only when needed: where sources disagree or the claim is contested. Omit otherwise.>

## Related

[[other-lesson-id]], [[another-id]]
```

Omit `## Related` if nothing relates.

## Verify before anything is indexed

The session that mined the lessons is the worst judge of them. Once the new lesson files are
written, spawn a **fresh** subagent (never a fork: a fork inherits this context and grades its
own work) with each new lesson's path and the source it cites. It reports, lesson by lesson,
whether the source supports the TL;DR and How to apply, and whether the timestamp lands near
the idea. Check every lesson if there are fewer than 10, otherwise at least a fifth of them
plus every lesson with a caveat. Correct or delete what it flags.

Only then update `INDEX.md` and the ledger. A source goes into `.processed.json` once its
lessons are on disk and verified. This order is required: an interrupted run must not leave a
source marked as mined when its lessons never made it.

**Recovering an interrupted run:** active lessons on disk that `INDEX.md` doesn't list were
never verified. Before mining anything new, put them through the verification step above, then
index them. Don't count them as "already known" when deduplicating new candidates.

## INDEX.md format

```markdown
# <Topic title> lessons

<N> active lessons from <K> sources. Generated by /extract-lessons; read this first.

## <Category>

- [<Title>](<category>/<id>.md) (<level>): <one-line hook>.

## Extraction runs

- <YYYY-MM-DD>: <N> new, <M> superseded, <K> sources mined, <D> candidates dropped as duplicates or low signal, <V> checked by verification, <X> corrected or dropped.
```

Keep earlier run lines below the new one, newest first.

## Report

Keep it short: lessons written per category, superseded, sources mined, candidates dropped,
the verification counts, and three standout lesson titles. Then the next step: `/path <topic>`
to lay the lessons out as a learning path, and `/quiz <topic>` to start learning them.
