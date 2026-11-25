from pyjinhx import BaseComponent
from tests.fixtures.fewer_files.domain import Tone


class StatusDot(BaseComponent):
    tone: Tone = Tone.CALM
