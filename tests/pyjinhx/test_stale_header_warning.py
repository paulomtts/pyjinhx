"""L1.4.4 — the one-time stale ``{#def#}`` header warning.

A hand-written BaseComponent subclass whose resolved template still carries a
``{#def#}`` header gets one WARNING, ever: the class-based path ignores that
header, so it is dead weight the author should delete.

The header probe itself runs once per class, at descriptor build; these tests
pin both halves — the frozen flag and the render-time dedup.

Fixture templates live beside this module so ``_template_candidate`` resolves
them from the class name:
  - ``stale_card.pjx``  — has a ``{#def#}`` header
  - ``stale_badge.pjx`` — has none
"""

import logging
from pathlib import Path

from pyjinhx import props_header
from pyjinhx._component import BaseComponent
from pyjinhx.descriptor import ClassDescriptor
from pyjinhx.props_header import build_component_class, parse_props_header
from pyjinhx.rendering import render_level

_TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class StaleCard(BaseComponent):
    """Hand-written class whose co-located template carries a {#def#} header."""

    title: str = "default"


class StaleBadge(BaseComponent):
    """Hand-written class whose co-located template carries no header."""

    text: str = "OK"


def test_hand_written_class_with_header_sets_flag():
    """A header in the resolved template lands as has_stale_def_header=True."""
    assert StaleCard.__pjx_descriptor__.template_path == (
        Path(__file__).parent / "stale_card.pjx"
    )
    assert StaleCard.__pjx_descriptor__.has_stale_def_header is True


def test_hand_written_class_without_header_leaves_flag_false():
    """No header in the resolved template leaves the flag False."""
    assert StaleBadge.__pjx_descriptor__.has_stale_def_header is False


def test_unreadable_template_leaves_flag_false():
    """A class whose template does not exist on disk must not raise here."""

    class NoTemplateAtAll(BaseComponent):
        pass

    assert NoTemplateAtAll.__pjx_descriptor__.has_stale_def_header is False


def _wire(cls: type[BaseComponent], *, stale: bool) -> None:
    """Point ``cls`` at a loadable template and pin its stale-header flag.

    The real descriptor's template_path is an absolute path to a ``.pjx``
    file, which the test session's loader would still resolve by name; the
    render-path tests care only about the flag, so they swap in a descriptor
    naming a template under tests/templates instead.
    """
    cls.__pjx_descriptor__ = ClassDescriptor(
        template_path=_TEMPLATE_DIR / "stale_render.html",
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=True,
        provenance={"template": cls},
        has_stale_def_header=stale,
    )
    cls._pjx_stale_header_warned = False


def test_render_warns_once_for_stale_header(render_session, caplog):
    """First render of a flagged class emits exactly one naming WARNING."""

    class WarnOnce(BaseComponent):
        title: str = "Hi"

    _wire(WarnOnce, stale=True)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        render_level(WarnOnce(), render_session)

    stale = [r for r in caplog.records if "{#def#}" in r.getMessage()]
    assert len(stale) == 1, [r.getMessage() for r in stale]
    assert stale[0].levelno == logging.WARNING
    assert "WarnOnce" in stale[0].getMessage()


def test_second_render_does_not_warn_again(render_session, caplog):
    """The warning is once per class, not once per render."""

    class WarnOnlyOnce(BaseComponent):
        title: str = "Hi"

    _wire(WarnOnlyOnce, stale=True)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        render_level(WarnOnlyOnce(), render_session)
        render_level(WarnOnlyOnce(), render_session)

    stale = [r for r in caplog.records if "{#def#}" in r.getMessage()]
    assert len(stale) == 1, [r.getMessage() for r in stale]


def test_no_header_never_warns(render_session, caplog):
    """A class whose template has no header stays silent across renders."""

    class NeverWarns(BaseComponent):
        title: str = "Hi"

    _wire(NeverWarns, stale=False)

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        render_level(NeverWarns(), render_session)
        render_level(NeverWarns(), render_session)

    assert [r for r in caplog.records if "{#def#}" in r.getMessage()] == []


def test_classless_component_never_warns(render_session, caplog):
    """A class built *from* a header is not carrying a stale one."""
    fields = parse_props_header('{#def title: str = "x" #}\n<div>{{ title }}</div>')
    assert fields is not None
    cls = build_component_class(fields, "StaleClassless")

    assert cls.__pjx_descriptor__.has_stale_def_header is False

    cls.__pjx_descriptor__ = ClassDescriptor(
        template_path=_TEMPLATE_DIR / "stale_render.html",
        slot_fields=frozenset(),
        children_field=None,
        css_paths=(),
        js_paths=(),
        strict=False,
        provenance={"template": cls},
        has_stale_def_header=cls.__pjx_descriptor__.has_stale_def_header,
    )

    with caplog.at_level(logging.WARNING, logger="pyjinhx"):
        render_level(cls(), render_session)
        render_level(cls(), render_session)

    assert [r for r in caplog.records if "{#def#}" in r.getMessage()] == []


def test_header_is_parsed_once_per_class_not_per_render(render_session, monkeypatch):
    """N renders of a class cost zero header parses: the probe ran at build."""

    class ProbeOnce(BaseComponent):
        title: str = "Hi"

    _wire(ProbeOnce, stale=False)

    calls: list[str] = []

    def _spy(source: str):
        calls.append(source)
        return parse_props_header(source)

    monkeypatch.setattr(props_header, "parse_props_header", _spy)

    for _ in range(5):
        render_level(ProbeOnce(), render_session)

    assert calls == []


def test_probe_runs_exactly_once_at_class_definition(monkeypatch):
    """Defining a class parses its template header once, and only once."""
    calls: list[str] = []

    def _spy(source: str):
        calls.append(source)
        return parse_props_header(source)

    monkeypatch.setattr(props_header, "parse_props_header", _spy)

    class ProbedOnce(StaleCard):
        """Inherits StaleCard's header-bearing template via the MRO walk."""

    assert ProbedOnce.__pjx_descriptor__.has_stale_def_header is True
    assert len(calls) == 1
