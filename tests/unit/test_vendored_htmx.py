from pyjinhx.utils import read_vendored_htmx


def test_returns_vendored_htmx_library_source():
    src = read_vendored_htmx()
    # the vendored htmx library defines the global
    assert "var htmx" in src


def test_guarded_against_double_load():
    # If the page already loaded htmx (e.g. user added it themselves), our
    # inlined copy must no-op rather than redefine it.
    src = read_vendored_htmx()
    assert "if (!window.htmx)" in src
