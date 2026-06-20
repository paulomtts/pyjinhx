"""The react class keyword: MutationKey-strict, replacing reacts_to."""

from typing import ClassVar

import pytest

from pyjinhx import MutationKey, ReactiveComponent, mutates


class Keys(MutationKey):
    NAVBAR = "navbar"
    TODOS = "todos"


def test_react_keyword_populates_reacts_to():
    class Navbar(ReactiveComponent, react={Keys.NAVBAR}):
        @classmethod
        def load(cls) -> "Navbar":
            return cls()

    assert Navbar._pjx_reacts_to == frozenset({"navbar"})


def test_react_rejects_bare_strings():
    with pytest.raises(TypeError, match="MutationKey"):
        class Bad(ReactiveComponent, react={"navbar"}):
            @classmethod
            def load(cls) -> "Bad":
                return cls()


def test_react_rejects_bare_member_without_set():
    with pytest.raises(TypeError, match="set of MutationKey members"):
        class Bare(ReactiveComponent, react=Keys.NAVBAR):
            @classmethod
            def load(cls) -> "Bare":
                return cls()


def test_react_rejects_mixed_valid_and_invalid():
    with pytest.raises(TypeError, match="'navbar'"):
        class Mixed(ReactiveComponent, react={Keys.TODOS, "navbar"}):
            @classmethod
            def load(cls) -> "Mixed":
                return cls()


def test_reacts_to_classvar_rejected():
    with pytest.raises(TypeError, match="react class keyword"):
        class OldKeyword(ReactiveComponent):
            reacts_to: ClassVar[set] = {Keys.NAVBAR}

            @classmethod
            def load(cls) -> "OldKeyword":
                return cls()


def test_subclass_inherits_react_keys():
    class ReactParent(ReactiveComponent, react={Keys.TODOS}):
        @classmethod
        def load(cls) -> "ReactParent":
            return cls()

    class ReactChild(ReactParent):
        @classmethod
        def load(cls) -> "ReactChild":
            return cls()

    assert ReactChild._pjx_reacts_to == frozenset({"todos"})


def test_load_without_react_keys_rejected():
    with pytest.raises(TypeError, match="no react keys"):
        class NoKeys(ReactiveComponent):
            @classmethod
            def load(cls) -> "NoKeys":
                return cls()


def test_mutates_rejects_bare_strings():
    with pytest.raises(TypeError, match="MutationKey"):
        @mutates("todos")  # type: ignore[arg-type]  # deliberately passes a bare string
        def save():
            pass


def test_mutates_accepts_members():
    @mutates(Keys.TODOS)
    def save():
        return "ok"

    assert save() == "ok"
