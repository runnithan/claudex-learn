# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Changed

- YouTube transcripts are fetched with ordinary requests instead of a Chrome-impersonating client (`curl_cffi` is no longer a dependency). The README now explains that the transcript library is unofficial, what YouTube's terms say, and how to paste a transcript by hand instead.

### Added

- `/new-topic`: records a learner's goal, level and what their practice looks like in `topics/<topic>/topic.md`.
- `/add-source`: adds YouTube URLs (timestamped transcripts), article URLs (readable text as markdown), local files or pasted text to a topic.
- `/extract-lessons`: mines sources into one-idea lesson files cited to the source and video timestamp, with supersession, deduplication and a fresh-subagent verification pass.
- `/path`: arranges a topic's lessons into beginner-to-advanced stages and shows progress through them.
- `/quiz`: spaced-repetition quizzing (Leitner boxes), one application question at a time.
- `/review`: feedback on the learner's own work measured against the lessons, which also queues the lessons behind each suggested change for the next quiz.
- `scripts/fetch_sources.py`, `scripts/srs.py` and `scripts/validate.py`, with tests and a CI workflow.
- `.claude/settings.json` pre-approving only those three scripts (once the folder is trusted), so `/quiz` can record answers across turns without a prompt each time.
- A chess example topic.
