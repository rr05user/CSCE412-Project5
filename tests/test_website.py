"""Deterministic pre-deployment tests for the existing Project 5 static site.

Run with: python -m pytest -q tests
"""
from __future__ import annotations

from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = (ROOT / "website").resolve()
PAGES = (
    "index.html",
    "about.html",
    "projects.html",
    "skills.html",
    "contact.html",
)
DOMAIN = "csce412rahul021005.me"


class ExtractHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self.tags: set[str] = set()
        self.title_text = ""
        self.in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        if tag == "title":
            self.in_title = True
        attr = dict(attrs)
        if tag in {"a", "link"} and attr.get("href"):
            self.links.append((tag, attr["href"]))
        if tag in {"script", "img", "source"} and attr.get("src"):
            self.links.append((tag, attr["src"]))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_text += data


def parse_page(filename: str) -> ExtractHTML:
    parser = ExtractHTML()
    parser.feed((SITE / filename).read_text(encoding="utf-8"))
    parser.close()
    return parser


def local_target(page: Path, url: str) -> Path | None:
    """Resolve an internal URL to its on-disk artifact; ignore external URLs."""
    ref = urlsplit(url.strip())
    if ref.scheme and ref.scheme.lower() not in {"http", "https"}:
        return None  # mailto:, tel:, data:, javascript:, etc.
    if ref.netloc and ref.hostname not in {DOMAIN, "www." + DOMAIN}:
        return None
    if not ref.path and ref.fragment:
        return None  # same-page anchor
    if not ref.path and not ref.netloc:
        return None
    path = unquote(ref.path)
    if path.startswith("/") or ref.netloc:
        target = SITE / path.lstrip("/")
    else:
        target = page.parent / path
    target = target.resolve()
    if not target.is_relative_to(SITE):
        raise AssertionError(f"Asset/link escapes the website directory: {url}")
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target


def test_required_pages_exist() -> None:
    missing = [f for f in PAGES if not (SITE / f).is_file()]
    assert not missing, f"Required website pages missing: {missing}"


@pytest.mark.parametrize("page_name", PAGES)
def test_page_structure(page_name: str) -> None:
    path = SITE / page_name
    assert path.is_file(), f"Missing page: {path}"
    html = path.read_text(encoding="utf-8")
    parsed = parse_page(page_name)
    assert re.search(r"<!doctype\s+html", html, re.IGNORECASE), f"{page_name}: missing HTML5 doctype"
    assert {"html", "head", "body", "title"} <= parsed.tags, f"{page_name}: missing essential HTML tags"
    assert parsed.title_text.strip(), f"{page_name}: title must not be empty"
    assert "nav" in parsed.tags, f"{page_name}: missing navigation element"


@pytest.mark.parametrize("page_name", PAGES)
def test_internal_links_and_assets(page_name: str) -> None:
    page_path = SITE / page_name
    assert page_path.is_file(), f"Missing page: {page_name}"
    broken: list[str] = []
    for tag, url in parse_page(page_name).links:
        target = local_target(page_path, url)
        if target is not None and not target.is_file():
            broken.append(f"<{tag}> {url} (expected {target.relative_to(SITE)})")
    assert not broken, f"{page_name} has broken internal links/assets:\n" + "\n".join(broken)


def test_required_static_assets() -> None:
    assert (SITE / "assets" / "site.js").is_file(), "Required theme-switcher script assets/site.js is missing"
    css = list(SITE.rglob("*.css"))
    assert css, "No CSS stylesheet found under website/"


def test_release_matches_source_commit() -> None:
    manifest_path = SITE / "release.json"
    assert manifest_path.is_file(), "release.json missing: run python scripts/make_release.py first"
    release = json.loads(manifest_path.read_text(encoding="utf-8"))
    sha = release.get("source_commit", "")
    assert re.fullmatch(r"[0-9a-f]{40}", sha), "source_commit must be a full Git commit SHA"
    assert release.get("release_id") == sha, "release_id and source_commit do not match"
    assert release.get("generated_utc"), "Missing release generation timestamp"
