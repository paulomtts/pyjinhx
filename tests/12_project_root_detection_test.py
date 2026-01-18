import os

from pyjinhx.finder import Finder


def test_detect_root_directory_finds_pyproject():
    root_dir = Finder.detect_root_directory()

    assert os.path.exists(root_dir)
    assert os.path.exists(os.path.join(root_dir, "pyproject.toml"))

