"""#1026: a tier-2 cache hit on an ancestor feeds its nested child a stale load key.

The shape is a shell that reacts to something broad (``view``) wrapping content
that reacts to something narrower (``conversation``), with the shell threading
the narrow value down as the child's load key. Dirtying the narrow key evicts
the child's entry but not the shell's, so the next request rebuilds the child
from the shell's stale field.

These tests pin the *mechanism*, because the mechanism is not what it looks
like from the outside: the child's ``load()`` is not skipped. It runs, and it
returns the current truth for whatever key it was handed — which is the stale
one. Anything that fixes this has to make the ancestor's entry stop surviving a
dirtied descendant key; re-rendering the nested region on a hit would change
nothing, since it already re-renders.
"""

import dataclasses
from typing import Annotated

import pytest

from pyjinhx import discovery
from pyjinhx.config import configure_pyjinhx, current_settings
from pyjinhx.reactive.backend import InMemoryCacheBackend
from pyjinhx.reactive.cache import invalidate
from pyjinhx.reactive.component import PjxKey, ReactiveComponent
from pyjinhx.rendering import render
from pyjinhx.session import request_scope

STORE = {"conversation": "1"}
CHILD_LOAD_KEYS: list[str] = []
PARENT_LOADS: list[None] = []


class NestedChild(ReactiveComponent, react=("conversation",)):
    """Content keyed by the conversation it belongs to."""

    conversation: Annotated[str, PjxKey()] = ""
    body: str = ""

    @classmethod
    def load(cls, conversation: str) -> "NestedChild":
        CHILD_LOAD_KEYS.append(conversation)
        return cls(conversation=conversation, body=f"messages-of-{conversation}")


class BroadShell(ReactiveComponent, react=("view",)):
    """A shell that reads `conversation` but only reacts to `view`."""

    conversation: str = ""

    @classmethod
    def load(cls) -> "BroadShell":
        PARENT_LOADS.append(None)
        return cls(id="shell", conversation=STORE["conversation"])


@pytest.fixture(autouse=True)
def _publish(tmp_path):
    """Register the pair against real templates and a fresh tier-2 backend."""
    STORE["conversation"] = "1"
    CHILD_LOAD_KEYS.clear()
    PARENT_LOADS.clear()

    shell = tmp_path / "broad_shell.pjx"
    shell.write_text(
        '<div id="{{ id }}"><NestedChild id="child" conversation="{{ conversation }}"/></div>'
    )
    child = tmp_path / "nested_child.pjx"
    child.write_text('<section id="{{ id }}">{{ body }}</section>')
    discovery.build_registry(tmp_path, [BroadShell, NestedChild])
    # build_registry probes each class's defining module dir, not tmp_path, so
    # the descriptors are repointed at the files written above.
    BroadShell.__pjx_descriptor__ = dataclasses.replace(
        BroadShell.__pjx_descriptor__, template_path=shell
    )
    NestedChild.__pjx_descriptor__ = dataclasses.replace(
        NestedChild.__pjx_descriptor__, template_path=child
    )

    previous = current_settings()
    configure_pyjinhx(previous.merge(cache_backend=InMemoryCacheBackend()))
    yield
    configure_pyjinhx(previous)


def _first_request() -> str:
    """One request with the store on conversation 1, warming both tier-2 entries."""
    with request_scope():
        return render(BroadShell(id="shell"))


def _second_request() -> str:
    """A later request, after the store moved on and `conversation` was dirtied.

    A fresh scope, so tier 1 is empty and only the cross-request tier answers.
    invalidate() stands in for what the response composer does with the
    request's dirtied keys.
    """
    with request_scope():
        invalidate(["conversation"])
        return render(BroadShell(id="shell"))


def test_the_shells_entry_survives_a_dirtied_key_only_its_child_reacts_to():
    """The shell is served from tier 2 because no dirtied key is tagged on it."""
    _first_request()
    STORE["conversation"] = "2"
    PARENT_LOADS.clear()

    _second_request()

    assert PARENT_LOADS == []


def test_the_nested_child_still_loads_but_against_the_shells_stale_key():
    """The child's load() is reached — with the key the stale shell handed down.

    This is the fact the issue's problem statement gets wrong. A non-empty list
    here is positive proof that no cached subtree replayed verbatim: the shell's
    template re-rendered and re-filled its child hole. The child did real work
    and answered correctly. It was asked about the wrong conversation.
    """
    _first_request()
    STORE["conversation"] = "2"
    CHILD_LOAD_KEYS.clear()

    _second_request()

    assert CHILD_LOAD_KEYS == ["1"]


def test_a_cache_opt_out_on_the_child_does_not_rescue_it():
    """cache=False on the child changes nothing: its caching was never the problem.

    Declared inline rather than on the module's NestedChild so the opt-out is
    the only difference from the test above.
    """

    class OptedOutChild(ReactiveComponent, react=("conversation",), cache=False):
        conversation: Annotated[str, PjxKey()] = ""
        body: str = ""

        @classmethod
        def load(cls, conversation: str) -> "OptedOutChild":
            CHILD_LOAD_KEYS.append(conversation)
            return cls(conversation=conversation, body=f"messages-of-{conversation}")

    template = NestedChild.__pjx_descriptor__.template_path
    assert template is not None
    OptedOutChild.__pjx_descriptor__ = dataclasses.replace(
        OptedOutChild.__pjx_descriptor__, template_path=template
    )
    discovery.build_registry(template.parent, [BroadShell, OptedOutChild])
    shell_template = BroadShell.__pjx_descriptor__.template_path
    assert shell_template is not None
    shell_template.write_text(
        '<div id="{{ id }}"><OptedOutChild id="child" conversation="{{ conversation }}"/></div>'
    )

    _first_request()
    STORE["conversation"] = "2"
    CHILD_LOAD_KEYS.clear()

    _second_request()

    assert CHILD_LOAD_KEYS == ["1"]


def test_a_shell_reacting_to_its_childs_key_too_stays_correct():
    """The control: make the shell's react set a superset and the staleness goes.

    This is suggested fix 1 simulated by hand, and it is why that fix is the one
    that addresses this — not the walk-the-cached-tree option, which would leave
    the stale key flowing down untouched.
    """

    class SupersetShell(ReactiveComponent, react=("view", "conversation")):
        conversation: str = ""

        @classmethod
        def load(cls) -> "SupersetShell":
            return cls(id="shell", conversation=STORE["conversation"])

    template = BroadShell.__pjx_descriptor__.template_path
    assert template is not None
    SupersetShell.__pjx_descriptor__ = dataclasses.replace(
        SupersetShell.__pjx_descriptor__, template_path=template
    )
    discovery.build_registry(template.parent, [SupersetShell, NestedChild])

    with request_scope():
        render(SupersetShell(id="shell"))
    STORE["conversation"] = "2"
    CHILD_LOAD_KEYS.clear()
    with request_scope():
        invalidate(["conversation"])
        html = render(SupersetShell(id="shell"))

    assert CHILD_LOAD_KEYS == ["2"]
    assert "messages-of-2" in html


@pytest.mark.xfail(
    reason="#1026: the shell's tier-2 entry is not tagged with its nested "
    "child's react keys, so a dirtied 'conversation' never evicts it",
    strict=True,
)
def test_dirtying_a_nested_regions_key_reaches_that_region():
    """What should happen, and does not yet. Flips to a pass when #1026 lands."""
    _first_request()
    STORE["conversation"] = "2"

    html = _second_request()

    assert "messages-of-2" in html
