# claudex-learn

[![ci](https://github.com/runnithan/claudex-learn/actions/workflows/ci.yml/badge.svg)](https://github.com/runnithan/claudex-learn/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Learn any topic from the sources you pick, inside [Claude Code](https://claude.com/claude-code).**

Give it YouTube links, article URLs or your own notes. claudex-learn turns them into short
lessons that each cite where they came from, down to the minute of the video. Then it lays them
out as a learning path, quizzes you with spaced repetition, and reviews your own practice work
against what you've learned.

It's the sibling of [claudex-setup](https://github.com/runnithan/claudex-setup), which does the
same thing for Claude Code setups. This one works for anything: chess, guitar, investing,
Spanish, a programming language.

## Quickstart

**Requirements:** Claude Code and [`uv`](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/runnithan/claudex-learn
cd claudex-learn && uv sync     # then open Claude Code here
```

The first time you open it, Claude Code asks whether you trust the folder. The dialog lists what
`.claude/settings.json` allows: the repo's own three scripts (`srs.py`, `validate.py`,
`fetch_sources.py`) and nothing else. Accept it, and quizzes can save your progress without a
permission prompt on every answer.

```text
/new-topic guitar                              # your goal, your level, what your practice looks like
/add-source guitar https://youtu.be/...        # a video, an article URL, a file, or pasted text
/extract-lessons guitar                        # sources become cited lessons
/path guitar                                   # lessons become stages, and you see where you are
/quiz guitar                                   # spaced-repetition questions, one at a time
/review guitar my-practice-log.md              # feedback on your own work, against the lessons
```

Between commands, just ask questions. Claude answers from your topic's lessons first and links
to the source.

## How it works

```text
 sources (videos, articles, notes)
        │  /add-source
        ▼
 topics/<topic>/sources/*.md ──/extract-lessons──▶ lessons/<category>/<id>.md
                                                        │
                            ┌───────────────────────────┼──────────────────────────┐
                            ▼                           ▼                          ▼
                     /path: stages,              /quiz: spaced            /review: your work,
                     beginner first              repetition               checked against lessons
                                                        ▲                          │
                                                        └──── lessons to drill ────┘
```

- **One idea per lesson.** A video listing ten principles becomes ten lessons, each with a
  TL;DR, why it matters, how to apply it, and a "check yourself" question.
- **Every lesson cites its source.** Video citations jump to the timestamp where the idea is taught.
- **Checked before it's kept.** A fresh subagent verifies new lessons against their sources
  before they enter the library, and newer advice supersedes older advice instead of piling up.
- **Quizzes favour applying over reciting.** Questions are scenarios ("what would you do
  here?"), graded against the lesson. Anything you miss comes back sooner.
- **Review closes the loop.** `/review` points at specific places in your work, names the lesson
  each change comes from, and queues those lessons for your next quiz.

## Commands

| Run | To |
|-----|----|
| `/new-topic <name>` | start a topic: goal, level, and what your practice work looks like |
| `/add-source <topic> <url \| file \| text>` | add a YouTube video, a web article, a local file or pasted text |
| `/extract-lessons <topic>` | mine new sources into cited, verified lessons |
| `/path <topic>` | build or refresh the learning path and show your progress |
| `/quiz <topic> [n]` | a spaced-repetition session (reviews due first, then new lessons) |
| `/review <topic> <file \| text>` | feedback on your own work, measured against the lessons |

## Sources

- **YouTube videos:** saved as transcripts with a `[m:ss]` marker about every minute, in
  English when there's an English track and in the video's own language otherwise. Videos with
  no captions are listed in `sources/unavailable.txt` and skipped from then on.
- **Web articles:** the readable text is extracted as markdown. Paywalled or JavaScript-only
  pages can fail (they're listed in `unavailable.txt` too); paste the text instead.
- **Pasted text and files:** saved verbatim, so lessons can cite them.
- **Not yet supported:** playlists (paste the individual videos instead).

YouTube throttles heavy transcript fetching, so the fetcher spaces its requests out and stops
after three blocked requests. Run it again later and it picks up where it stopped.

## About YouTube transcripts

YouTube has no official way to download captions for videos you don't own: its API's caption
download [requires permission to edit the video](https://developers.google.com/youtube/v3/docs/captions/download).
So `fetch_sources.py` uses the community
[`youtube-transcript-api`](https://github.com/jdepoix/youtube-transcript-api) library, which
reads the same captions the YouTube player shows. It's unofficial, and YouTube's
[Terms of Service](https://www.youtube.com/t/terms) restrict automated access, so use it for
your own learning, gently, and at your own discretion.

To keep that footprint small:

- It makes ordinary requests, waits a few seconds between videos, and stops after three
  blocked requests.
- Transcripts stay on your machine (they're gitignored). Only your lessons, which are short
  summaries that link back to the video, get committed.

If you'd rather not fetch automatically, open the video on YouTube, click **Show transcript**
below the description, copy the text, and paste it in with `/add-source <topic> <pasted text>`.

## What stays on your machine

`.gitignore` keeps each topic's source files (transcripts and articles belong to their authors),
your quiz progress (`progress.json`) and your reviews private. Lessons, the learning path and
`topic.md` are committed, so a topic can be shared without its sources.

## The chess example

`topics/chess/` ships with 50 lessons mined from three YouTube videos and one Wikipedia article,
arranged into a six-stage path for a beginner who hangs pieces and runs out of ideas after the
opening. `/review` works without a chess engine: its read of plans and principles is the useful
part, and any concrete move line it suggests is worth checking in a free engine such as lichess
analysis. To try it:

```text
uv run scripts/fetch_sources.py chess    # re-fetch its sources (needed only for /extract-lessons)
/path chess
/quiz chess
```

## Layout

```text
topics/<topic>/
  topic.md                goal, level, categories, what practice looks like
  sources/urls.txt        the URLs to fetch (committed)
  sources/*.md            fetched or pasted sources (gitignored)
  lessons/INDEX.md        every active lesson, by category
  lessons/<category>/     one file per lesson
  path.md                 the learning path
  progress.json           your quiz state (gitignored)
  reviews/                saved /review feedback (gitignored)
.claude/commands/         the six commands
scripts/                  fetch_sources.py, srs.py, validate.py
```

## Development

```bash
uv run pytest -q                 # unit tests
uv run scripts/validate.py       # commands, topics and lesson libraries are well-formed
```

CI runs both on every push and pull request. Changes are logged in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
