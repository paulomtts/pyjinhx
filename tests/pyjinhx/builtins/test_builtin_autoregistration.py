"""End-to-end: a user template mounting builtin tags resolves with no manual
register_class call (issue #738) — setup(components_root=...) alone is enough.
"""

import pytest

from pyjinhx import discovery


@pytest.fixture(autouse=True)
def reset_registry():
    """discovery._registry is process-global; don't leak a builtins-populated
    mapping into whichever test module runs next in the same process."""
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None
    yield
    discovery._registry.mapping = {}
    discovery._registry.template_dir = None


def test_nested_builtin_tags_expand_after_setup_alone(tmp_path):
    """A user template using <PJXCard><PJXCardBody> renders with no register_class call."""
    import pyjinhx.builtins  # noqa: F401
    from pyjinhx.classless import component
    from pyjinhx.config import setup
    from pyjinhx.rendering import render
    from pyjinhx.session import RenderSession

    (tmp_path / "user_page.pjx").write_text(
        "<PJXCard><PJXCardBody>hello</PJXCardBody></PJXCard>"
    )
    setup(app=None, components_root=tmp_path)

    UserPage = component("UserPage")
    html = render(UserPage(), RenderSession())  # pyright: ignore[reportCallIssue]

    assert "hello" in html
    assert 'class="pjx-card' in html  # pjx_card.pjx's actual emitted markup
    assert "PJXCard" not in html
