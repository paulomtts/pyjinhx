"""Shared helpers for reactive render tests."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

from pyjinhx import MutationKey
from pyjinhx.client import ClientBackend
from pyjinhx.integrations.fastapi import FastAPIClientBackend
from pyjinhx.mutations import MutationTracker


class Keys(MutationKey):
    TODOS = "todos"


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


@contextmanager
def reactive_client(
    manifest: Sequence[Mapping[str, object]] | None = None,
    *,
    extra_headers: dict[str, str] | None = None,
    trigger_id: str | None = None,
) -> Iterator[FastAPIClientBackend]:
    headers = dict(extra_headers or {})
    if manifest is not None:
        headers["X-PJX-Mounted"] = json.dumps(manifest)
    if trigger_id is not None:
        headers["X-PJX-Trigger"] = json.dumps({"id": trigger_id})
    backend = FastAPIClientBackend(FakeRequest(headers))
    with ClientBackend.scope(backend):
        yield backend


def record_mutation(*keys: str) -> None:
    MutationTracker.record(keys)
