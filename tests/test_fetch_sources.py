from types import SimpleNamespace

import pytest

import fetch_sources as fs
from common import read_frontmatter


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.youtube.com/watch?v=jfcVjIa1EGM", ("youtube", "jfcVjIa1EGM")),
        ("https://youtu.be/jfcVjIa1EGM?t=30", ("youtube", "jfcVjIa1EGM")),
        ("https://m.youtube.com/watch?v=jfcVjIa1EGM&list=PL123", ("youtube", "jfcVjIa1EGM")),
        ("https://www.youtube.com/shorts/jfcVjIa1EGM", ("youtube", "jfcVjIa1EGM")),
        ("https://www.youtube.com/playlist?list=PL123", ("playlist", "https://www.youtube.com/playlist?list=PL123")),
        ("https://en.wikipedia.org/wiki/Chess#Rules", ("web", "https://en.wikipedia.org/wiki/Chess")),
        ("ftp://example.com/file", ("invalid", "not an http(s) URL")),
        ("https://www.youtube.com/@SomeChannel", ("invalid", "YouTube link without a video id")),
    ],
)
def test_classify(url, expected):
    assert fs.classify(url) == expected


def test_youtube_links_to_the_same_video_share_a_key():
    assert fs.source_key("https://youtu.be/jfcVjIa1EGM") == fs.source_key(
        "https://www.youtube.com/watch?v=jfcVjIa1EGM&t=90s"
    )


def test_format_transcript_groups_by_minute_with_timestamps():
    snips = [SimpleNamespace(text=t, start=s) for t, s in [("a", 0.2), ("b", 30), ("c", 61), ("d\nsplit", 3605)]]
    assert fs.format_transcript(snips) == "[0:00] a b\n\n[1:01] c\n\n[1:00:05] d split"


def test_add_urls_skips_duplicates_by_key_and_rejects_unusable(tmp_path):
    urls = tmp_path / "urls.txt"
    added, rejected = fs.add_urls(urls, ["https://a.com/x", "https://youtu.be/jfcVjIa1EGM"])
    assert added == ["https://a.com/x", "https://youtu.be/jfcVjIa1EGM"] and rejected == []
    added, rejected = fs.add_urls(
        urls,
        [
            "https://a.com/x#section",
            "https://www.youtube.com/watch?v=jfcVjIa1EGM",
            "https://www.youtube.com/playlist?list=PL1",
            "not a url",
            "https://c.com/z",
        ],
    )
    assert added == ["https://c.com/z"]
    assert [u for u, _ in rejected] == ["https://www.youtube.com/playlist?list=PL1", "not a url"]
    assert fs.load_urls(urls) == ["https://a.com/x", "https://youtu.be/jfcVjIa1EGM", "https://c.com/z"]


def track(code, generated):
    return SimpleNamespace(language_code=code, is_generated=generated)


def test_pick_track_prefers_english_then_hand_made():
    assert fs.pick_track([]) is None
    assert fs.pick_track([track("es", False), track("en", True)]).language_code == "en"
    assert fs.pick_track([track("en", True), track("en-GB", False)]).language_code == "en-GB"
    only_spanish = fs.pick_track([track("es", True), track("es-419", False)])
    assert (only_spanish.language_code, only_spanish.is_generated) == ("es-419", False)


def test_add_file_copies_verbatim_with_exact_word_count(tmp_path):
    src = tmp_path / "notes.md"
    src.write_text("# My notes: openings\n\nControl the centre early.\n", encoding="utf-8")
    sources = tmp_path / "sources"
    sources.mkdir()
    out = fs.add_file(sources, src, None, "https://example.com/post")
    meta, body = read_frontmatter(out)
    assert meta["title"] == "My notes: openings" and meta["url"] == "https://example.com/post"
    assert meta["words"] == 8 and body.strip() == src.read_text(encoding="utf-8").strip()  # same as `wc -w`
    assert fs.existing_keys(sources) == {"https://example.com/post"}


class FakeFetch:
    """Stands in for the network: maps video ids to a result or an exception."""

    def __init__(self, outcomes):
        self.outcomes, self.calls = outcomes, []

    def __call__(self, video_id):
        self.calls.append(video_id)
        outcome = self.outcomes[video_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome, "en"


@pytest.fixture
def offline(monkeypatch):
    monkeypatch.setattr(fs, "FETCH_SLEEP_MAX", 0)
    monkeypatch.setattr(fs, "youtube_metadata", lambda vid: (f"Video {vid}", "Channel"))


def test_fetch_urls_saves_skips_and_records(tmp_path, offline, monkeypatch):
    ids = ["aaaaaaaaaaa", "bbbbbbbbbbb", "ccccccccccc"]
    fake = FakeFetch({ids[0]: "[0:00] hi", ids[1]: fs.NoTracks("none"), ids[2]: "[0:00] again"})
    monkeypatch.setattr(fs, "fetch_youtube", fake)
    urls = [f"https://youtu.be/{i}" for i in ids] + [f"https://www.youtube.com/watch?v={ids[0]}"]

    counts = fs.fetch_urls(tmp_path, urls)
    assert (counts["saved"], counts["unavailable"], counts["already"]) == (2, 1, 1)
    assert fs.load_unavailable(tmp_path / "unavailable.txt") == {f"yt:{ids[1]}"}

    fake.calls.clear()
    counts = fs.fetch_urls(tmp_path, urls)  # second run: nothing touches the network
    assert fake.calls == [] and (counts["already"], counts["unavailable"]) == (3, 1)


def test_fetch_urls_stops_after_block_limit(tmp_path, offline, monkeypatch):
    ids = [c * 11 for c in "defgh"]
    fake = FakeFetch({i: fs.Blocked("throttled") for i in ids})
    monkeypatch.setattr(fs, "fetch_youtube", fake)
    counts = fs.fetch_urls(tmp_path, [f"https://youtu.be/{i}" for i in ids])
    assert counts["blocked"] == fs.BLOCK_LIMIT and len(fake.calls) == fs.BLOCK_LIMIT
    assert not (tmp_path / "unavailable.txt").exists()  # throttling is never recorded as permanent


def test_written_source_is_found_again_as_existing(tmp_path):
    meta = {"title": 'A "quoted": title', "type": "youtube", "url": "https://www.youtube.com/watch?v=jfcVjIa1EGM"}
    first = fs.write_source(tmp_path, "same-name", meta, "body")
    second = fs.write_source(tmp_path, "same-name", {**meta, "url": "https://example.com/"}, "body")
    assert (first.name, second.name) == ("same-name.md", "same-name-2.md")
    assert read_frontmatter(first)[0]["title"] == 'A "quoted": title'
    assert fs.existing_keys(tmp_path) == {"yt:jfcVjIa1EGM", "https://example.com/"}


def test_unavailable_ledger_round_trip(tmp_path):
    ledger = tmp_path / "unavailable.txt"
    fs.record_unavailable(ledger, "https://www.youtube.com/watch?v=jfcVjIa1EGM", "NoTracks", "Title\twith\nodd chars")
    fs.record_unavailable(ledger, "https://paywalled.example/post", "no readable text", "https://paywalled.example/post")
    assert fs.load_unavailable(ledger) == {"yt:jfcVjIa1EGM", "https://paywalled.example/post"}
