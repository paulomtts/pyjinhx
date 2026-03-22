import tempfile
from pathlib import Path

from pyjinhx import Renderer
from pyjinhx.builtins import Modal


def test_builtins_modal_loads_adjacent_template_outside_loader_root():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        Renderer.set_default_environment(tmp_path)
        modal = Modal(id="m", title="Hi", body="There")
        rendered = str(modal.render())
        assert 'class="px-modal"' in rendered
        assert "Hi" in rendered
        assert "There" in rendered
