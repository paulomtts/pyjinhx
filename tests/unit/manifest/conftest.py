"""Fixtures shared by the split test files in this folder."""

import pytest

from tests.unit.manifest._helpers import BADGE, CARD_PY, CHIP, TODO_COUNT, _write


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A project of one component of each kind, with the cwd at its root."""
    _write(
        tmp_path,
        {
            "app/__init__.py": "",
            "app/ui/__init__.py": "",
            "app/ui/badge.pjx": BADGE,
            "app/ui/todo_count.pjx": TODO_COUNT,
            "app/ui/chip.py": CHIP,
            "app/ui/card.py": CARD_PY,
            "app/ui/card.pjx": "<p>{{ title }}</p>\n",
        },
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path
