---
description: "Add learning material to a topic: YouTube or article URLs (saved as a transcript or markdown), a local file, or text pasted into the chat."
argument-hint: "<topic> <url(s) | file path | pasted text>"
allowed-tools: Read, Write, Glob, Bash(uv run scripts/fetch_sources.py:*), Bash(ls:*)
---

# /add-source: give a topic something to learn from

Arguments: `$ARGUMENTS`

**Topic:** the first word names a folder in `topics/`. If it matches none and exactly one
topic exists, use that one and treat the whole argument string as the material. Otherwise list
the topics and ask which one.

## Result

The material is saved under `topics/<topic>/sources/` as markdown the lesson miner can read, and
the learner knows how many sources are waiting to be mined.

What to do depends on what follows the topic:

- **One or more http(s) URLs:** run `uv run scripts/fetch_sources.py <topic> --url <url> [<url> ...]`.
  YouTube links become timestamped transcripts; other links become the article text. Relay its
  summary line, plus any SKIP, FAILED, BLOCKED, NO TRANSCRIPT or NO TEXT lines with the fix it
  suggests. Exit code 1 means some URLs failed or YouTube throttled the requests: report it,
  don't retry in a loop. For a page it couldn't read, offer to take the article as pasted text.
- **A path to an existing `.md` or `.txt` file:** run
  `uv run scripts/fetch_sources.py <topic> --file <path>`, adding `--source-url <url>` if the
  learner says where the text came from and `--title "<title>"` if the file has no heading. The
  script copies the file byte for byte and adds frontmatter with an exact word count.
- **Anything else is pasted text:** save it to `sources/<slug>.md`, where `<slug>` is the title
  in kebab-case with `-2`, `-3` added if that name is taken.
- **Nothing:** explain the three options in a few lines.

Pasted text is kept **verbatim**. Don't summarise, tidy or trim it: the miner cites it, and a
lesson must trace back to what the source actually said. Put this frontmatter above it (quote
the title so a colon in it can't break the YAML):

```markdown
---
title: "<first heading, else the first line, else ask>"
type: pasted
url: <original URL, only if the learner gave one>
added: <YYYY-MM-DD>
---
```

When the text replaces an article URL the fetcher couldn't read, include that URL as `url:`.
The fetcher then treats the URL as done instead of retrying it. Never overwrite an existing source.

## Done when

Finish with one line: how many sources `topics/<topic>/sources/` holds, and how many are not
yet mined (source files whose `sources/<file>.md` path is missing from
`lessons/.processed.json`). Then: "Run `/extract-lessons <topic>` once you've added everything."
