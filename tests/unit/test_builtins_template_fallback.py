import tempfile
from pathlib import Path

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModal


def test_builtins_modal_loads_adjacent_template_outside_loader_root():
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            Renderer.set_default_environment(tmp_path)
            modal = PJXModal(id="m", title="Hi", body="There")
            rendered = str(modal.render())
            assert 'class="pjx-modal"' in rendered
            assert "Hi" in rendered
            assert "There" in rendered
    finally:
        Renderer.set_default_environment(None)
