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


def test_cli_writes_stub_adjacent_and_gitignores(tmp_path):
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
    # stub sits NEXT TO the .pjx so intra-package imports resolve
    stub = comp / "counter.pyi"
    assert stub.exists()
    assert "class Counter(BaseComponent):" in stub.read_text()
    # gitignored via a managed block listing the generated stub (repo-relative)
    gitignore = (tmp_path / ".gitignore").read_text()
    assert "pyjinhx generated stubs" in gitignore
    assert "app/components/counter.pyi" in gitignore
    # --check is clean immediately after a write
    check = subprocess.run(
        [_sys.executable, "-m", "pyjinhx.stubgen", str(tmp_path), "--check"],
        capture_output=True, text=True,
    )
    assert check.returncode == 0


def test_check_flag_detects_stale(tmp_path):
    comp = tmp_path / "pkg"
    comp.mkdir()
    (comp / "w.pjx").write_text(
        "{# python\nfrom pyjinhx import BaseComponent\n"
        "class W(BaseComponent):\n    n: int\n#}\n<p>{{ n }}</p>\n"
    )
    # never generated → --check must fail (non-zero)
    check = subprocess.run(
        [_sys.executable, "-m", "pyjinhx.stubgen", str(tmp_path), "--check"],
        capture_output=True, text=True,
    )
    assert check.returncode == 1
