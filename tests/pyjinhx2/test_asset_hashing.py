"""L2.2.4: content-hash filenames and the hashing asset URL resolver."""

import hashlib
import os
import re
from pathlib import Path

import pytest

from pyjinhx2.assets import hashed_filename

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
