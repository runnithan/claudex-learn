#!/usr/bin/env python3
"""Fetch a topic's sources into markdown files the lesson miner can read.

Usage:
    uv run scripts/fetch_sources.py <topic>                  # fetch everything pending in urls.txt
    uv run scripts/fetch_sources.py <topic> --url URL [...]  # add URLs to urls.txt, then fetch
    uv run scripts/fetch_sources.py <topic> --file PATH [--title T] [--source-url URL]
                                                             # copy a local .md/.txt file in verbatim

YouTube links become timestamped transcripts (English if there is an English track,
otherwise the video's own language). Any other link becomes the article's text as
markdown. Each lands in topics/<topic>/sources/<slug>.md with frontmatter (title,
type, url, creator, fetched, words). URLs already fetched are skipped, so reruns are
cheap. Sources that can't be fetched go in sources/unavailable.txt and are skipped
until you delete their line.
"""

import argparse
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import yaml

from common import first_heading, read_frontmatter, slugify, topic_dir

try:
    import requests
    import trafilatura
    from youtube_transcript_api import (
        AgeRestricted,
        InvalidVideoId,
        NoTranscriptFound,
        PoTokenRequired,
        RequestBlocked,
        TranscriptsDisabled,
        VideoUnavailable,
        VideoUnplayable,
        YouTubeRequestFailed,
        YouTubeTranscriptApi,
    )
except ImportError as e:
    print(f"Missing dependency: {e.name}. Run `uv sync` in the repo root first.", file=sys.stderr)
    sys.exit(1)


class NoTracks(Exception):
    """The video lists no caption tracks in any language."""


# The video genuinely has no fetchable transcript: record it and never retry.
PERMANENT_ERRORS = (
    NoTracks,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
    VideoUnplayable,
    AgeRestricted,
    InvalidVideoId,
)
# Throttling, or a YouTube experiment on this client (PoTokenRequired): retry on a
# later run, and count toward the breaker.
TRANSIENT_ERRORS = (RequestBlocked, YouTubeRequestFailed, PoTokenRequired)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _env_number(name: str, default: float) -> float:
    """Read a numeric env override, ignoring invalid values rather than crashing."""
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# A throttled response can trickle bytes slowly, and a socket timeout only bounds
# the gap between bytes, so a hard wall-clock deadline wraps each whole fetch.
REQUEST_TIMEOUT = 12
FETCH_DEADLINE = 20
ARTICLE_DEADLINE = 45
# Stop after this many new YouTube transcripts in one run, and wait a few seconds
# between fetches, so a long list doesn't hammer YouTube.
MAX_PER_RUN = int(_env_number("MAX_TRANSCRIPTS_PER_RUN", 40))
FETCH_SLEEP_MIN = _env_number("FETCH_SLEEP_MIN", 4)
FETCH_SLEEP_MAX = _env_number("FETCH_SLEEP_MAX", 8)
BLOCK_LIMIT = 3
MIN_ARTICLE_WORDS = 150
PARAGRAPH_SECONDS = 60

URLS_HEADER = (
    "# One URL per line: YouTube videos or web articles.\n"
    "# Lines starting with # are ignored. Run /add-source or\n"
    "# `uv run scripts/fetch_sources.py <topic>` to fetch them.\n\n"
)
UNAVAILABLE_HEADER = (
    "# Sources that could not be fetched (no captions, paywall, page gone).\n"
    "# fetch_sources.py skips these on every run. Delete a line to retry it.\n"
    "# date<TAB>url<TAB>reason<TAB>title\n"
)


class Blocked(Exception):
    """A fetch timed out or was refused: probably throttling, worth retrying later."""


class NoReadableText(Exception):
    """An article page had no extractable text (paywall, login wall, JS-only page)."""


def classify(url: str) -> tuple[str, str]:
    """Return (kind, key): ('youtube', video_id), ('playlist', url), ('web', url) or ('invalid', reason)."""
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return "invalid", "not an http(s) URL"
    host = parsed.netloc.lower().split(":")[0]
    if host in YOUTUBE_HOSTS:
        query = urllib.parse.parse_qs(parsed.query)
        candidate = None
        if host == "youtu.be":
            candidate = parsed.path.strip("/").split("/")[0]
        elif "v" in query:
            candidate = query["v"][0]
        else:
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
                candidate = parts[1]
        if candidate and VIDEO_ID.match(candidate):
            return "youtube", candidate
        if "list" in query:
            return "playlist", url.strip()
        return "invalid", "YouTube link without a video id"
    return "web", urllib.parse.urlunparse(parsed._replace(fragment=""))


def source_key(url: str) -> str | None:
    """Dedupe key for a URL: the video id for YouTube, the fragment-less URL otherwise."""
    kind, key = classify(url)
    if kind == "youtube":
        return f"yt:{key}"
    if kind == "web":
        return key
    return None


def existing_keys(sources_dir: Path) -> set[str]:
    """Dedupe keys of every source file already on disk (read from frontmatter `url`)."""
    keys = set()
    for path in sources_dir.glob("*.md"):
        try:
            meta, _ = read_frontmatter(path)
        except (ValueError, yaml.YAMLError):
            continue
        url = meta.get("url")
        if isinstance(url, str):
            key = source_key(url)
            if key:
                keys.add(key)
    return keys


def load_urls(urls_file: Path) -> list[str]:
    if not urls_file.exists():
        return []
    lines = urls_file.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def add_urls(urls_file: Path, new_urls: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Append fetchable URLs not already listed (compared by source key).

    Returns (added, rejected), where rejected pairs each unusable URL with the reason.
    """
    if not urls_file.exists():
        urls_file.write_text(URLS_HEADER, encoding="utf-8")
    listed = {source_key(u) for u in load_urls(urls_file)}
    added, rejected = [], []
    for url in (u.strip() for u in new_urls):
        if not url:
            continue
        kind, detail = classify(url)
        if kind == "playlist":
            rejected.append((url, "playlists are not supported yet, paste the individual video URLs"))
            continue
        if kind == "invalid":
            rejected.append((url, detail))
            continue
        key = source_key(url)
        if key not in listed:
            listed.add(key)
            added.append(url)
    if added:
        text = urls_file.read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            text += "\n"
        urls_file.write_text(text + "\n".join(added) + "\n", encoding="utf-8")
    return added, rejected


def load_unavailable(path: Path) -> set[str]:
    """Source keys listed in the unavailable ledger."""
    if not path.exists():
        return set()
    keys = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and not line.startswith("#"):
            key = source_key(parts[1])
            if key:
                keys.add(key)
    return keys


def record_unavailable(path: Path, url: str, reason: str, title: str) -> None:
    if not path.exists():
        path.write_text(UNAVAILABLE_HEADER, encoding="utf-8")
    clean = " ".join(title.split())
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"{date.today()}\t{url}\t{reason}\t{clean}\n")


def with_deadline(fn, seconds: float):
    """Run fn() but give up after `seconds` of wall-clock time, whatever the socket does.

    The worker is a daemon thread, so one stuck in a hung socket is abandoned and dies
    with the process. The breaker caps how many can pile up in a run.
    """
    box = {}

    def worker():
        try:
            box["value"] = fn()
        except BaseException as e:  # re-raised in the caller's thread below
            box["error"] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(seconds)
    if thread.is_alive():
        raise TimeoutError(f"no response within {seconds}s")
    if "error" in box:
        raise box["error"]
    return box["value"]


class _TimeoutSession(requests.Session):
    """A plain requests session that always applies a timeout."""

    def request(self, *args, **kwargs):
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        return super().request(*args, **kwargs)


def youtube_metadata(video_id: str) -> tuple[str, str]:
    """(title, channel) from YouTube's public oEmbed endpoint.

    A 4xx means the video is private, removed or not embeddable: fall back to a
    placeholder and let the transcript fetch decide. Anything else (timeouts, 429,
    5xx) raises Blocked, so the source is retried later rather than saved under a
    placeholder title that would change its filename on the next fetch.
    """
    watch = f"https://www.youtube.com/watch?v={video_id}"
    query = urllib.parse.urlencode({"url": watch, "format": "json"})
    try:
        with urllib.request.urlopen(f"https://www.youtube.com/oembed?{query}", timeout=15) as resp:
            data = json.load(resp)
        return data.get("title") or f"YouTube video {video_id}", data.get("author_name") or "unknown"
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            return f"YouTube video {video_id}", "unknown"
        raise Blocked(f"oEmbed HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise Blocked(f"oEmbed: {e}") from e


def timestamp(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_transcript(snippets, every: int = PARAGRAPH_SECONDS) -> str:
    """Group caption snippets into paragraphs of roughly `every` seconds, each led by [m:ss].

    The markers let lessons cite the moment (url&t=<seconds>s) instead of a whole video.
    """
    paragraphs, current, start = [], [], None
    for snip in snippets:
        text = " ".join(snip.text.split())
        if not text:
            continue
        if start is None:
            start = snip.start
        elif snip.start - start >= every:
            paragraphs.append(f"[{timestamp(start)}] " + " ".join(current))
            current, start = [], snip.start
        current.append(text)
    if current:
        paragraphs.append(f"[{timestamp(start)}] " + " ".join(current))
    return "\n\n".join(paragraphs)


def pick_track(tracks):
    """English first (hand-made before auto-generated), then any hand-made track, then any other."""
    tracks = list(tracks)
    if not tracks:
        return None
    return min(tracks, key=lambda t: (t.language_code.split("-")[0].lower() != "en", t.is_generated))


def fetch_youtube(video_id: str) -> tuple[str, str]:
    """(timestamped transcript, language code). Raises Blocked on timeouts and throttling."""

    def _fetch():
        track = pick_track(YouTubeTranscriptApi(http_client=_TimeoutSession()).list(video_id))
        if track is None:
            raise NoTracks("no caption tracks")
        return track.fetch(), track.language_code

    try:
        snippets, language = with_deadline(_fetch, FETCH_DEADLINE)
    except (TimeoutError, requests.exceptions.RequestException) as e:
        raise Blocked(str(e)) from e
    except TRANSIENT_ERRORS as e:
        raise Blocked(type(e).__name__) from e
    return format_transcript(snippets), language


def fetch_article(url: str) -> tuple[str, str, str]:
    """(title, site, markdown) for a web article. Raises NoReadableText or Blocked."""

    def _fetch():
        return trafilatura.fetch_url(url)

    try:
        html = with_deadline(_fetch, ARTICLE_DEADLINE)
    except TimeoutError as e:
        raise Blocked(str(e)) from e
    if not html:
        raise NoReadableText("page could not be downloaded")
    text = trafilatura.extract(html, output_format="markdown", url=url, include_tables=True, include_links=False)
    if not text or len(text.split()) < MIN_ARTICLE_WORDS:
        raise NoReadableText("no readable article text (paywall, login wall or a JavaScript-only page?)")
    meta = trafilatura.extract_metadata(html, default_url=url)
    host = urllib.parse.urlparse(url).netloc.removeprefix("www.")
    title = (meta.title if meta and meta.title else None) or host
    site = (meta.sitename if meta and meta.sitename else None) or host
    return title, site, text


def unique_path(sources_dir: Path, base: str) -> Path:
    """sources/<base>.md, or <base>-2.md, -3... if that name is taken."""
    base = base or "source"
    path = sources_dir / f"{base}.md"
    n = 2
    while path.exists():
        path = sources_dir / f"{base}-{n}.md"
        n += 1
    return path


def write_source(sources_dir: Path, base: str, meta: dict, body: str) -> Path:
    """Write a source file with YAML frontmatter under a name no other source uses."""
    path = unique_path(sources_dir, base)
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
    path.write_text(f"---\n{front}---\n\n{body.strip()}\n", encoding="utf-8")
    return path


def add_file(sources_dir: Path, file: Path, title: str | None, source_url: str | None) -> Path:
    """Copy a local text file in verbatim, adding frontmatter when it has none."""
    text = file.read_text(encoding="utf-8")
    try:
        meta, body = read_frontmatter(file)
    except (ValueError, yaml.YAMLError):
        meta, body = {}, text
    if meta:
        target = unique_path(sources_dir, slugify(str(meta.get("title") or file.stem), 70))
        target.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        return target
    first_line = next((line.strip("# ").strip() for line in body.splitlines() if line.strip()), "")
    title = title or first_heading(body) or first_line[:100] or file.stem
    meta = {"title": title, "type": "file"}
    if source_url:
        meta["url"] = source_url
    meta.update({"added": str(date.today()), "words": len(body.split())})
    return write_source(sources_dir, slugify(title, 70), meta, body)


def fetch_urls(sources_dir: Path, urls: list[str]) -> dict:
    """Fetch every URL not already on disk or in the unavailable ledger. Returns counts."""
    unavailable_file = sources_dir / "unavailable.txt"
    have = existing_keys(sources_dir)
    unavailable = load_unavailable(unavailable_file)
    counts = {"saved": 0, "already": 0, "unavailable": 0, "failed": 0, "blocked": 0, "unsupported": 0}
    yt_fetches = 0

    for url in urls:
        kind, key = classify(url)
        if kind in ("invalid", "playlist"):
            why = "playlists are not supported yet, paste the individual video URLs" if kind == "playlist" else key
            print(f"- SKIP {url}: {why}")
            counts["unsupported"] += 1
            continue
        dedupe = source_key(url)
        if dedupe in have:
            counts["already"] += 1
            continue
        if dedupe in unavailable:
            counts["unavailable"] += 1
            continue

        if kind == "youtube":
            if yt_fetches >= MAX_PER_RUN:
                print(f"- Reached {MAX_PER_RUN} transcripts this run; the rest fetch next run.")
                break
            if yt_fetches and FETCH_SLEEP_MAX > 0:
                time.sleep(random.uniform(FETCH_SLEEP_MIN, FETCH_SLEEP_MAX))
            yt_fetches += 1
            watch = f"https://www.youtube.com/watch?v={key}"
            try:
                title, creator = youtube_metadata(key)
                body, language = fetch_youtube(key)
            except Blocked as e:
                counts["blocked"] += 1
                print(f"- BLOCKED {url}: {e} (YouTube may be throttling you; rerun later)")
                if counts["blocked"] >= BLOCK_LIMIT:
                    print(f"- {BLOCK_LIMIT} blocked requests: stopping early. Rerun later to fetch the rest.")
                    break
                continue
            except PERMANENT_ERRORS as e:
                record_unavailable(unavailable_file, watch, type(e).__name__, title)
                counts["unavailable"] += 1
                print(f"- NO TRANSCRIPT {title}: {type(e).__name__} (listed in sources/unavailable.txt)")
                continue
            except Exception as e:
                counts["failed"] += 1
                print(f"- FAILED {url}: {e}")
                continue
            meta = {
                "title": title,
                "type": "youtube",
                "url": watch,
                "creator": creator,
                "language": language,
                "fetched": str(date.today()),
                "words": len(body.split()),
            }
            path = write_source(sources_dir, f"{slugify(title, 70)}-{key}".lstrip("-"), meta, f"# {title}\n\n{body}")
        else:
            try:
                title, site, body = fetch_article(key)
            except NoReadableText as e:
                record_unavailable(unavailable_file, key, str(e), key)
                counts["unavailable"] += 1
                print(
                    f"- NO TEXT {url}: {e}. Listed in sources/unavailable.txt. Save the article as a file and "
                    f"add it with --file PATH --source-url {key} instead."
                )
                continue
            except Blocked as e:
                counts["blocked"] += 1
                print(f"- BLOCKED {url}: {e} (rerun later)")
                continue
            except Exception as e:
                counts["failed"] += 1
                print(f"- FAILED {url}: {e}")
                continue
            meta = {
                "title": title,
                "type": "article",
                "url": key,
                "creator": site,
                "fetched": str(date.today()),
                "words": len(body.split()),
            }
            path = write_source(sources_dir, slugify(title, 70) or "article", meta, body)

        have.add(dedupe)
        counts["saved"] += 1
        print(f"- SAVED {path.name} ({meta['words']:,} words)")
    return counts


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        # Windows pipes default to a legacy code page that can't print emoji or non-Latin titles.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Fetch a topic's sources into markdown.")
    parser.add_argument("topic", help="topic folder name under topics/")
    parser.add_argument("--url", nargs="+", default=[], help="URL(s) to add to urls.txt before fetching")
    parser.add_argument("--file", type=Path, help="a local .md or .txt file to copy in verbatim")
    parser.add_argument("--title", help="title for --file when it has no frontmatter")
    parser.add_argument("--source-url", help="where the --file text came from, if it has a URL")
    args = parser.parse_args()

    tdir = topic_dir(args.topic)
    sources_dir = tdir / "sources"
    sources_dir.mkdir(exist_ok=True)
    urls_file = sources_dir / "urls.txt"

    if args.file:
        if not args.file.is_file():
            print(f"No file at {args.file}", file=sys.stderr)
            return 2
        key = source_key(args.source_url) if args.source_url else None
        if key and key in existing_keys(sources_dir):
            print(f"Already have a source for {args.source_url}; nothing copied.")
            return 0
        path = add_file(sources_dir, args.file, args.title, args.source_url)
        meta, _ = read_frontmatter(path)
        print(f"- SAVED {path.name} ({meta.get('words', '?')} words)")
        return 0

    if args.url:
        added, rejected = add_urls(urls_file, args.url)
        for url, why in rejected:
            print(f"- SKIP {url}: {why}")
        print(f"Added {len(added)} new URL(s) to sources/urls.txt")

    urls = load_urls(urls_file)
    if not urls:
        print(f"No URLs in {urls_file}. Add some (one per line) or pass --url.")
        return 0

    counts = fetch_urls(sources_dir, urls)
    print(
        "\nDone: {saved} saved, {already} already fetched, {unavailable} unavailable, "
        "{failed} failed, {blocked} blocked, {unsupported} unsupported.".format(**counts)
    )
    return 1 if counts["failed"] or counts["blocked"] else 0


if __name__ == "__main__":
    sys.exit(main())
