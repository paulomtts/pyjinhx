"""PJXProgress renders a progress bar / loading indicator (port of v0.x pyjinhx/builtins/ui/pjx_progress)."""

import pytest
from pydantic import ValidationError

from pyjinhx2.builtins.ui.pjx_progress import PJXProgress
from pyjinhx2.render import render
from pyjinhx2.session import RenderSession


@pytest.fixture
def progress_session():
    """Loader rooted at "/" so absolute descriptor template paths resolve.

    ClassDescriptor.template_path is absolute and render() feeds it straight to
    the session's FileSystemLoader; Jinja only resolves an absolute path when
    the loader root is "/". Same fixture shape as tests/pyjinhx2/builtins/pjx_divider.
    """
    return RenderSession(template_dir="/")


def _html(session, **kw) -> str:
    return render(PJXProgress(id="p", **kw), session)


def test_default_render_is_indeterminate(progress_session):
    html = _html(progress_session)
    assert html.count("<div") == 1
    assert html.count("<progress") == 1
    assert 'value="' not in html
    assert "aria-valuenow" not in html
    assert 'aria-label="Loading"' in html
    assert 'class="pjx-progress"' in html
    assert 'id="p"' in html


def test_valued_render_sets_aria_and_value(progress_session):
    html = _html(progress_session, value=40, max=80)
    assert 'value="40.0"' in html
    assert 'aria-valuenow="40.0"' in html
    assert 'aria-valuemin="0"' in html
    assert 'aria-valuemax="80.0"' in html


def test_label_renders_span_and_aria_labelledby(progress_session):
    html = _html(progress_session, label="Uploading")
    assert 'id="p-label"' in html
    assert 'class="pjx-progress__label"' in html
    assert ">Uploading<" in html
    assert 'aria-labelledby="p-label"' in html
    assert "aria-label=" not in html


def test_loading_label_used_only_without_label_and_value(progress_session):
    html = _html(progress_session, loading_label="Please wait")
    assert 'aria-label="Please wait"' in html

    labeled = _html(progress_session, loading_label="Please wait", label="Uploading")
    assert "Please wait" not in labeled


def test_class_name_appended(progress_session):
    html = _html(progress_session, class_name="mine")
    assert 'class="pjx-progress mine"' in html


def test_empty_class_name_adds_nothing(progress_session):
    html = _html(progress_session, class_name="")
    assert 'class="pjx-progress"' in html


def test_label_renders_escaped_text(progress_session):
    html = _html(progress_session, label="<script>x</script>")
    assert "&lt;script&gt;x&lt;/script&gt;" in html
    assert "<script>" not in html


def test_invalid_value_type_is_rejected():
    with pytest.raises(ValidationError):
        PJXProgress(id="p", value="not-a-number")  # pyright: ignore[reportArgumentType]


def test_undeclared_attr_is_rejected():
    """v2 core is strict (extra="forbid"): v0.x's extra_attrs pass-through is gone.

    Deliberate narrowing of v0.x behavior, matching the #500 precedent.
    """
    with pytest.raises(ValidationError):
        PJXProgress(id="p", extra_attrs={"data-x": "y"})  # pyright: ignore[reportCallIssue]
