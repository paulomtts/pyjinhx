import tempfile
from pathlib import Path

from pyjinhx import Renderer
from pyjinhx.builtins import PJXModal, PJXModalBody, PJXModalHeader


def test_builtins_modal_loads_adjacent_template_outside_loader_root():
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            Renderer.set_default_environment(tmp_path)
            header = str(PJXModalHeader(id="m-h", title="Hi").render())
            body = str(PJXModalBody(id="m-b", content="There").render())
            modal = PJXModal(id="m", content=header + body)
            rendered = str(modal.render())
            assert 'class="pjx-modal"' in rendered
            assert "Hi" in rendered
            assert "There" in rendered
    finally:
        Renderer.set_default_environment(None)
