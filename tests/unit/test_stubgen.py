from pyjinhx.stubgen import generate_stub


def test_strips_function_bodies():
    src = (
        "\n"
        "from pyjinhx import ReactiveComponent\n"
        "\n"
        "class Counter(ReactiveComponent):\n"
        "    remaining: int\n"
        "\n"
        "    @classmethod\n"
        "    def load(cls):\n"
        "        return cls(remaining=db.remaining())\n"
    )
    stub = generate_stub(src)
    assert "class Counter(ReactiveComponent):" in stub
    assert "remaining: int" in stub
    assert "def load(cls):" in stub
    assert "db.remaining()" not in stub  # body stripped
    assert "..." in stub


def test_preserves_imports_and_fields():
    src = "\nfrom pyjinhx import BaseComponent\nclass Card(BaseComponent):\n    title: str\n"
    stub = generate_stub(src)
    assert "from pyjinhx import BaseComponent" in stub
    assert "title: str" in stub


import subprocess
import sys as _sys


def test_cli_writes_stub_into_cache(tmp_path):
    comp = tmp_path / "app" / "components"
    comp.mkdir(parents=True)
    (comp / "counter.pjx").write_text(
        "{# python\nfrom pyjinhx import BaseComponent\n"
        "class Counter(BaseComponent):\n    n: int\n#}\n<p>{{ n }}</p>\n"
    )
    result = subprocess.run(
        [_sys.executable, "-m", "pyjinhx.stubgen", str(tmp_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    stub = tmp_path / ".pjx" / "stubs" / "app" / "components" / "counter.pyi"
    assert stub.exists()
    assert "class Counter(BaseComponent):" in stub.read_text()
    assert (tmp_path / ".pjx" / ".gitignore").read_text() == "*\n"
    # --check is clean immediately after a write
    check = subprocess.run(
        [_sys.executable, "-m", "pyjinhx.stubgen", str(tmp_path), "--check"],
        capture_output=True, text=True,
    )
    assert check.returncode == 0
