from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger("pyjinhx")

PJX_MOUNTED_HEADER = "X-PJX-Mounted"
"""Name of the HTTP header carrying the client's mounted-region manifest."""

PJX_ASSETS_HEADER = "X-PJX-Assets"
"""Name of the HTTP header carrying asset URLs already loaded in the browser."""

PJX_TRIGGER_HEADER = "X-PJX-Trigger"
"""Name of the HTTP header carrying the data-pjx-id of the element that started the request."""

T = TypeVar("T")


def _parse_client_payload(
    client: object | str | list[Any] | None,
    *,
    header_name: str,
    header_getter: Callable[[object], object | None] | None = None,
    parse_value: Callable[[Any], T | None],
    empty_values: tuple[object, ...] = (None, ""),
) -> T | None:
    if client in empty_values:
        return None
    if not isinstance(client, (str, list)):
        try:
            header_value = client.headers.get(header_name)  # type: ignore[attr-defined]
        except AttributeError:
            if header_getter is not None:
                return header_getter(client)
            return None
        return _parse_client_payload(
            header_value,
            header_name=header_name,
            header_getter=header_getter,
            parse_value=parse_value,
            empty_values=empty_values,
        )
    if isinstance(client, str):
        try:
            parsed = json.loads(client)
        except json.JSONDecodeError:
            logger.warning("Could not parse %s as JSON; ignoring.", header_name)
            return None
        return parse_value(parsed)
    return parse_value(client)


class MountedManifest:
    @staticmethod
    def parse(
        mounted: str | list[dict[str, Any]] | object | None,
    ) -> list[dict[str, Any]]:
        def _coerce(parsed: Any) -> list[dict[str, Any]] | None:
            return parsed if isinstance(parsed, list) else None

        result = _parse_client_payload(
            mounted,
            header_name=PJX_MOUNTED_HEADER,
            parse_value=_coerce,
        )
        if result is not None:
            return result
        if mounted is not None and not isinstance(mounted, (str, list)):
            logger.warning(
                "mounted is not an %s header string, parsed list, request-like "
                "object, or None; ignoring.",
                PJX_MOUNTED_HEADER,
            )
        return []

    @staticmethod
    def is_present(client: str | list[dict[str, Any]] | object | None) -> bool:
        """
        Return whether the client already sent a valid ``X-PJX-Mounted`` manifest.

        A present header whose value parses to a JSON array (including ``[]``)
        means ``pjx.js`` is active in the browser.
        """
        if client is None:
            return False
        if isinstance(client, list):
            return True
        if isinstance(client, str):
            if client == "":
                return False
            try:
                parsed = json.loads(client)
            except json.JSONDecodeError:
                return False
            return isinstance(parsed, list)
        try:
            header_value = client.headers.get(PJX_MOUNTED_HEADER)  # type: ignore[attr-defined]
        except AttributeError:
            return False
        return MountedManifest.is_present(header_value)


class TriggerManifest:
    @staticmethod
    def parse(client: str | dict[str, Any] | object | None) -> dict[str, Any] | None:
        def _coerce(parsed: Any) -> dict[str, Any] | None:
            if isinstance(parsed, dict) and parsed.get("id"):
                return parsed
            return None

        return _parse_client_payload(
            client,
            header_name=PJX_TRIGGER_HEADER,
            parse_value=_coerce,
        )


class LoadedAssets:
    @staticmethod
    def parse(client: str | list[str] | object | None) -> frozenset[str]:
        def _coerce(parsed: Any) -> frozenset[str] | None:
            if isinstance(parsed, list):
                return frozenset(str(url) for url in parsed)
            return frozenset()

        result = _parse_client_payload(
            client,
            header_name=PJX_ASSETS_HEADER,
            parse_value=_coerce,
        )
        if result is not None:
            return result
        if isinstance(client, (list, tuple, set, frozenset)):
            return frozenset(str(url) for url in client)
        return frozenset()
