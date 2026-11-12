"""Demo registry for the component gallery: name -> (factory, iframe height px)."""

from demos import forms, graph, interaction, overlays, roster_picker, static

DEMOS = {
    **static.DEMOS,
    **overlays.DEMOS,
    **interaction.DEMOS,
    **forms.DEMOS,
    **graph.DEMOS,
    **roster_picker.DEMOS,
}

# Demos whose page needs the htmx + pjx.js runtime to work, not just to paint.
RUNTIME_DEMOS = frozenset({"PJXGraph", "PJXRosterPicker"})
