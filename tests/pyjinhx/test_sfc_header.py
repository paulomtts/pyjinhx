"""The stdlib-only half of reading a ``{#def#}`` signature."""

import pytest

from pyjinhx.sfc import HeaderSignatureError, header_arguments


def test_arguments_come_back_with_their_defaults():
    pairs = header_arguments('a: int, b: str = "x", c=pkg.mod.NAME, d=pkg.make()')

    assert [(arg.arg, default is not None) for arg, default in pairs] == [
        ("a", False),
        ("b", True),
        ("c", True),
        ("d", True),
    ]


@pytest.mark.parametrize(
    "signature",
    ["a, a", "*args", "**kw", "a, *, b", "a, /, b", "a=f(1)", "a=b", "a=pkg.f(x)"],
)
def test_what_a_header_may_not_hold_is_refused(signature):
    with pytest.raises(HeaderSignatureError) as refused:
        header_arguments(signature)

    assert refused.value.node is not None


def test_a_signature_that_does_not_parse_carries_the_syntax_error():
    with pytest.raises(HeaderSignatureError) as refused:
        header_arguments("a = 1, b")

    assert refused.value.syntax is not None
