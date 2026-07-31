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

from pathlib import Path

from pyjinhx2.component import BaseComponent


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
