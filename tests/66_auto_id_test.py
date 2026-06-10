import re

from pyjinhx import BaseComponent
from pyjinhx.builtins import Badge


def test_constructor_without_id_autogenerates():
    badge = Badge(label="hi")
    assert re.fullmatch(r"px-\d+", badge.id)


def test_constructor_with_empty_id_autogenerates():
    badge = Badge(id="", label="hi")
    assert re.fullmatch(r"px-\d+", badge.id)


def test_explicit_id_is_kept():
    badge = Badge(id="my-badge", label="hi")
    assert badge.id == "my-badge"


def test_auto_ids_are_unique():
    a = Badge(label="a")
    b = Badge(label="b")
    assert a.id != b.id


def test_subclass_inherits_auto_id():
    class AutoIdProbe(BaseComponent):
        pass

    probe = AutoIdProbe()
    assert re.fullmatch(r"px-\d+", probe.id)
