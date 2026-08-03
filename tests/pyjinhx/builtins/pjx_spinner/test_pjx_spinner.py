"""PJXSpinner renders a loading indicator (port of v0.x pyjinhx/builtins/ui/pjx_spinner)."""

import pytest
from pydantic import ValidationError

from pyjinhx.builtins.ui.pjx_spinner import PJXSpinner
from pyjinhx.rendering import render
from pyjinhx.session import RenderSession


@pytest.fixture
def spinner_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx/builtins/pjx_progress.
    """
    return RenderSession()


def _html(session, **kw) -> str:
    return render(PJXSpinner(id="s", **kw), session)


def test_default_render(spinner_session):
    html = _html(spinner_session)
    assert 'id="s"' in html
    assert 'class="pjx-spinner pjx-spinner--md"' in html
    assert 'role="status"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-busy="true"' in html
    assert 'class="pjx-spinner__ring" aria-hidden="true"' in html
    assert '<span class="pjx-spinner__label">Loading</span>' in html


@pytest.mark.parametrize("size", ["sm", "md", "lg"])
def test_size_variants(spinner_session, size):
    html = _html(spinner_session, size=size)
    assert f"pjx-spinner--{size}" in html


def test_invalid_size_is_rejected():
    with pytest.raises(ValidationError):
        PJXSpinner(id="s", size="huge")  # pyright: ignore[reportArgumentType]


def test_label_renders_escaped_text(spinner_session):
    html = _html(spinner_session, label="<script>x</script>")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_class_name_appended(spinner_session):
    html = _html(spinner_session, class_name="mine")
    assert 'class="pjx-spinner pjx-spinner--md mine"' in html


def test_empty_class_name_adds_nothing(spinner_session):
    html = _html(spinner_session, class_name="")
    assert 'class="pjx-spinner pjx-spinner--md"' in html


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #504 precedent.
    """
    with pytest.raises(ValidationError):
        PJXSpinner(id="s", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]
