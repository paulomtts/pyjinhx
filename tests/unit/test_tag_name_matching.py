import pytest

from pyjinhx.tags import RE_PASCAL_CASE_TAG_NAME


@pytest.mark.parametrize(
    "name", ["Avatar", "ButtonGroup", "PJXAvatar", "PJXAvatarStack", "HTMLBlock"]
)
def test_component_tag_names_match(name):
    assert RE_PASCAL_CASE_TAG_NAME.match(name)


@pytest.mark.parametrize("name", ["div", "DIV", "x", "X", "my-tag", "Has Space"])
def test_non_component_tag_names_rejected(name):
    assert not RE_PASCAL_CASE_TAG_NAME.match(name)
