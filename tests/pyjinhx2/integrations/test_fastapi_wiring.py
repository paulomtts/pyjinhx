"""The FastAPI adapter: request scope, header parsing, T1/T2 response adaptation."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pyjinhx2.component import BaseComponent
from pyjinhx2.integrations.fastapi import apply_setup
from pyjinhx2.config import PjxSettings


def test_apply_setup_is_importable():
    assert callable(apply_setup)
