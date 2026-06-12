import re

from pyjinhx import BaseComponent
from pyjinhx.builtins import PJXBadge


def test_constructor_without_id_autogenerates():
    badge = PJXBadge(label="hi")
    assert re.fullmatch(r"pjx-\d+", badge.id)


def test_constructor_with_empty_id_autogenerates():
    badge = PJXBadge(id="", label="hi")
    assert re.fullmatch(r"pjx-\d+", badge.id)


def test_explicit_id_is_kept():
    badge = PJXBadge(id="my-badge", label="hi")
    assert badge.id == "my-badge"


def test_auto_ids_are_unique():
    a = PJXBadge(label="a")
    b = PJXBadge(label="b")
    assert a.id != b.id


def test_subclass_inherits_auto_id():
    class AutoIdProbe(BaseComponent):
        pass

    probe = AutoIdProbe()
    assert re.fullmatch(r"pjx-\d+", probe.id)
