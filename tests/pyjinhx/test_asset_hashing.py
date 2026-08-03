"""L2.2.4: content-hash filenames and the hashing asset URL resolver."""

import hashlib
import os
import re
from pathlib import Path

import pytest

from pyjinhx.assets import asset_manifest, hashed_filename, resolver_with_hash
from pyjinhx.session import RenderSession

HEX8 = re.compile(r"^button\.[0-9a-f]{8}\.js$")


def _write(path: Path, text: str) -> Path:
    """Write text to path, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_hashed_filename_inserts_eight_hex_chars_between_stem_and_suffix(tmp_path):
    path = _write(tmp_path / "button.js", "console.log(1)")
    assert HEX8.match(hashed_filename(path))


def test_hashed_filename_digest_matches_sha256_of_file_bytes(tmp_path):
    path = _write(tmp_path / "button.js", "console.log(1)")
    expected = hashlib.sha256(b"console.log(1)").hexdigest()[:8]
    assert hashed_filename(path) == f"button.{expected}.js"


def test_hashed_filename_is_identical_for_identical_content_at_two_paths(tmp_path):
    a = _write(tmp_path / "a" / "button.js", "same bytes")
    b = _write(tmp_path / "b" / "button.js", "same bytes")
    assert hashed_filename(a) == hashed_filename(b)


def test_hashed_filename_changes_when_content_changes(tmp_path):
    path = _write(tmp_path / "button.js", "before")
    first = hashed_filename(path)
    path.write_text("after")
    # Bump mtime explicitly: the cache is keyed on it, and a same-second
    # rewrite can otherwise land on an unchanged timestamp.
    stat = path.stat()
    os.utime(path, (stat.st_atime + 10, stat.st_mtime + 10))
    assert hashed_filename(path) != first


def test_hashed_filename_respects_custom_hash_len(tmp_path):
    path = _write(tmp_path / "button.js", "console.log(1)")
    result = hashed_filename(path, hash_len=16)
    assert re.match(r"^button\.[0-9a-f]{16}\.js$", result)


def test_hashed_filename_raises_for_a_missing_file(tmp_path):
    with pytest.raises(OSError):
        hashed_filename(tmp_path / "nope.js")


def test_hashed_filename_handles_a_file_without_a_suffix(tmp_path):
    path = _write(tmp_path / "LICENSE", "text")
    digest = hashlib.sha256(b"text").hexdigest()[:8]
    assert hashed_filename(path) == f"LICENSE.{digest}"


def test_resolver_puts_a_top_level_file_directly_under_base_url(tmp_path):
    path = _write(tmp_path / "button.js", "console.log(1)")
    resolve = resolver_with_hash("/static", str(tmp_path))
    assert resolve(path) == f"/static/{hashed_filename(path)}"


def test_resolver_keeps_the_directory_relative_to_root(tmp_path):
    path = _write(tmp_path / "components" / "ui" / "button.js", "console.log(1)")
    resolve = resolver_with_hash("/static", str(tmp_path))
    assert resolve(path) == f"/static/components/ui/{hashed_filename(path)}"


def test_resolver_strips_a_trailing_slash_from_base_url(tmp_path):
    path = _write(tmp_path / "button.js", "console.log(1)")
    resolve = resolver_with_hash("https://cdn.example.com/", str(tmp_path))
    assert resolve(path) == f"https://cdn.example.com/{hashed_filename(path)}"


def test_resolver_raises_for_a_missing_file(tmp_path):
    resolve = resolver_with_hash("/static", str(tmp_path))
    with pytest.raises(OSError):
        resolve(tmp_path / "nope.js")


def _session() -> RenderSession:
    """A bare session; assets are set-added directly, no render needed."""
    return RenderSession()


def test_manifest_with_hashing_resolver_hashes_both_kinds_in_path_order(tmp_path):
    a_css = _write(tmp_path / "a.css", "a{}")
    b_css = _write(tmp_path / "nested" / "b.css", "b{}")
    y_js = _write(tmp_path / "y.js", "y")
    z_js = _write(tmp_path / "nested" / "z.js", "z")

    session = _session()
    session.css_assets.update({b_css, a_css})
    session.js_assets.update({z_js, y_js})

    manifest = asset_manifest(
        session, resolver=resolver_with_hash("/static", str(tmp_path))
    )

    assert manifest.stylesheets == (
        f"/static/{hashed_filename(a_css)}",
        f"/static/nested/{hashed_filename(b_css)}",
    )
    assert manifest.scripts == (
        f"/static/nested/{hashed_filename(z_js)}",
        f"/static/{hashed_filename(y_js)}",
    )
