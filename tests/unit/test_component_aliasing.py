"""Subclasses resolve to their ancestor's template and assets (MRO walk)."""

import pytest
from jinja2 import TemplateNotFound

from pyjinhx import BaseComponent, MutationKey, ReactiveComponent
from pyjinhx.builtins import PJXBadge, PJXCard

from tests.ui.aliasing.custom_badge import CustomBadge
from tests.ui.aliasing.fancy_badge import FancyBadge


class Keys(MutationKey):
    TASKS = "tasks"


class TaskBadge(PJXBadge):
    pass


def test_subclass_renders_base_template_and_assets():
    html = str(TaskBadge(label="3 open", color="brand").render())
    assert 'class="pjx-badge' in html              # PJXBadge's template
    assert "<style>" in html
    assert "--pjx-badge-radius-sm" in html         # PJXBadge's badge.css inlined


def test_css_only_override_replaces_just_the_css():
    html = str(FancyBadge(label="hi").render())
    assert 'class="pjx-badge' in html              # still PJXBadge's template
    assert "fancy-badge-marker" in html           # subclass css collected
    assert "--pjx-badge-radius-sm" not in html     # base badge.css NOT collected


def test_own_template_wins():
    html = str(CustomBadge(label="hi").render())
    assert "custom-badge-marker" in html          # subclass template used
    assert 'class="pjx-badge' not in html


def test_reactive_builtin_subclass_renders_and_stamps():
    class LiveBadge(ReactiveComponent, PJXBadge, react={Keys.TASKS}):
        @classmethod
        def load(cls) -> "LiveBadge":
            return cls(label="3 open", color="brand")

    html = str(LiveBadge.load().render())
    assert 'class="pjx-badge' in html
    assert "data-pjx" in html


def test_two_component_bases_rejected():
    with pytest.raises(TypeError, match="one component at a time"):
        class Both(PJXBadge, PJXCard):
            pass


def test_framework_plus_component_base_allowed():
    class Fine(ReactiveComponent, PJXBadge, react={Keys.TASKS}):
        @classmethod
        def load(cls) -> "Fine":
            return cls(label="x")

    assert Fine  # definition itself is the assertion


def test_missing_template_lists_mro_candidates():
    class NoTemplateBase(BaseComponent):
        pass

    class NoTemplateChild(NoTemplateBase):
        pass

    with pytest.raises(TemplateNotFound) as excinfo:
        NoTemplateChild().render()
    msg = str(excinfo.value)
    assert "no_template_child" in msg or "NoTemplateChild" in msg
    assert "no_template_base" in msg or "NoTemplateBase" in msg


def test_subclass_pascal_tag_renders():
    from pyjinhx import Renderer

    renderer = Renderer.get_default_renderer()
    html = str(renderer.render('<TaskBadge id="t1" label="hi"/>'))
    assert 'class="pjx-badge' in html
