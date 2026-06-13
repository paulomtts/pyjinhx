from pyjinhx.utils import pascal_case_to_kebab_case, pascal_case_to_snake_case


def test_snake_simple_pascal():
    assert pascal_case_to_snake_case("ButtonGroup") == "button_group"


def test_snake_single_word():
    assert pascal_case_to_snake_case("Avatar") == "avatar"


def test_snake_leading_acronym():
    assert pascal_case_to_snake_case("PJXAvatar") == "pjx_avatar"


def test_snake_leading_acronym_multiword():
    assert pascal_case_to_snake_case("PJXAvatarStack") == "pjx_avatar_stack"


def test_snake_embedded_acronym():
    assert pascal_case_to_snake_case("HTMLBlock") == "html_block"


def test_snake_trailing_acronym():
    assert pascal_case_to_snake_case("BlockHTML") == "block_html"


def test_snake_digits():
    assert pascal_case_to_snake_case("Grid2Col") == "grid2_col"


def test_snake_single_letter():
    assert pascal_case_to_snake_case("X") == "x"


def test_kebab_leading_acronym():
    assert pascal_case_to_kebab_case("PJXPanelTrigger") == "pjx-panel-trigger"


def test_kebab_simple():
    assert pascal_case_to_kebab_case("ButtonGroup") == "button-group"
