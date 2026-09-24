# claudex-learn

A Claude Code hub for learning any topic from sources the learner picks. YouTube videos, web
articles and pasted notes become short cited lessons, then a learning path, spaced-repetition
quizzes and feedback on the learner's own work.

## Layout

- `topics/<topic>/` holds one topic:
  - `topic.md`: goal, level, categories, and what practice looks like (read by every command).
  - `sources/`: `urls.txt` plus one markdown file per source. Gitignored except `urls.txt`.
  - `lessons/<category>/<id>.md`, with `lessons/INDEX.md` (read it first) and
    `lessons/.processed.json` (which sources have been mined).
  - `path.md`: the learning path. `progress.json` and `reviews/` are personal and gitignored.
- `.claude/commands/`: `/new-topic`, `/add-source`, `/extract-lessons`, `/path`, `/quiz`, `/review`.
- `scripts/`: `fetch_sources.py` (URLs to markdown), `srs.py` (quiz scheduling),
  `validate.py` (checks), `common.py`. Always run them with `uv run`.
- `topics/chess/` is the shipped example. Its lessons are public; its sources are not.

## Answering questions about a topic

When the learner asks about something a topic covers, answer from its lessons first: read
`topics/<topic>/lessons/INDEX.md`, open the relevant lessons, and cite them with their source
links. Say plainly when the library doesn't cover something, and label anything that comes from
outside it.

## Rules

- A lesson only says what its sources say. New lessons come from `/extract-lessons`, which cites
  and verifies them. Don't hand-write lessons into the library.
- `scripts/srs.py` owns quiz state. Never edit `progress.json` by hand.
- Never commit anything under a topic's `sources/` except `urls.txt`. Transcripts and articles
  belong to their authors, and `.gitignore` enforces this.
- Commands describe the finished result and how to check it, not a ritual of steps. Keep a fixed
  order only where the result depends on it (lessons verified before the ledger marks a source mined).

## Checks

Before calling a change done, both of these must pass (CI runs them too):

- `uv run pytest -q`
- `uv run scripts/validate.py`

## Commits and changelog

- Conventional Commits: `<type>(<scope>): <subject>`, imperative, lowercase, no trailing period.
- User-facing changes get a `CHANGELOG.md` entry (Keep a Changelog) in the same commit.
