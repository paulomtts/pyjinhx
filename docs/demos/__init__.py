"""Demo registry for the component gallery: name -> (factory, iframe height px)."""

from demos import forms, interaction, overlays, static

DEMOS = {**static.DEMOS, **overlays.DEMOS, **interaction.DEMOS, **forms.DEMOS}
