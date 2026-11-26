"""The `mro_dir` fixture for the ClassDescriptor tests."""

import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.unit.components.base._mro_module import _MRO_MODULE


@pytest.fixture
def mro_dir(tmp_path: Path) -> Iterator[Path]:
    """A real, file-backed module registered in sys.modules, plus its directory.

    Classes re-pointed at it with ``Cls.__module__ = _MRO_MODULE`` resolve their
    template candidates inside ``tmp_path``, so a test controls exactly which
    ancestors have a file on disk.
    """
    module = types.ModuleType(_MRO_MODULE)
    module.__file__ = str(tmp_path / f"{_MRO_MODULE}.py")
    sys.modules[_MRO_MODULE] = module
    try:
        yield tmp_path
    finally:
        del sys.modules[_MRO_MODULE]
