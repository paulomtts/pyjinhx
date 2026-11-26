"""Small presentational pieces that share a module."""

from pyjinhx import BaseComponent, Slot
from tests.fixtures.fewer_files.domain import Tone


class StatusDot(BaseComponent):
    tone: Tone = Tone.CALM

    template = r"""
    <i class="dot dot--{{ tone.value }}" aria-label="{{ tone.value }}"></i>
    {#css
    .dot { display: inline-block; width: 0.5rem; height: 0.5rem; }
    .dot--late { background: var(--danger); }
    #}
    """


class EmptyState(BaseComponent):
    """What a list shows with nothing in it; the icon slot takes raw markup."""

    message: str
    icon: Slot = ""

    template = r"""
    <div class="empty-state">{{ icon }}<p>{{ message }}</p></div>
    """
