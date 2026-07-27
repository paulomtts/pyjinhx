import pytest

from pyjinhx.tags import RE_PASCAL_CASE_TAG_NAME, contains_custom_tag


@pytest.mark.parametrize(
    "name", ["Avatar", "ButtonGroup", "PJXAvatar", "PJXAvatarStack", "HTMLBlock"]
)
def test_component_tag_names_match(name):
    assert RE_PASCAL_CASE_TAG_NAME.match(name)


@pytest.mark.parametrize("name", ["div", "DIV", "x", "X", "my-tag", "Has Space"])
def test_non_component_tag_names_rejected(name):
    assert not RE_PASCAL_CASE_TAG_NAME.match(name)


def test_contains_custom_tag_true_for_pascal_case_tag():
    assert contains_custom_tag('<div><MyButton id="x"/></div>') is True


def test_contains_custom_tag_false_for_plain_html():
    assert contains_custom_tag("<div><span>hello</span></div>") is False


def test_contains_custom_tag_false_for_no_angle_brackets():
    assert contains_custom_tag("just plain text, no tags") is False


def test_contains_custom_tag_false_for_lowercase_or_all_caps_tag():
    # lowercase tags, and all-caps (no lowercase letter), don't match the
    # PascalCase shape (mirrors RE_PASCAL_CASE_TAG_NAME's own constraints).
    assert contains_custom_tag("<div>5 < HTML </div>") is False
