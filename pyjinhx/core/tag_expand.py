from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Any

from .autodiscover import ComponentAutodiscover
from .parser import Parser
from .registry import Registry
from .tag import Tag

if TYPE_CHECKING:
    from .assets import RenderSession
    from .renderer import Renderer


def render_tag_node(
    renderer: Renderer,
    node: Tag | str,
    base_context: dict[str, Any],
    session: RenderSession,
    *,
    emit_assets: bool,
) -> str:
    if isinstance(node, str):
        return node

    rendered_children = "".join(
        render_tag_node(
            renderer,
            child,
            base_context=base_context,
            session=session,
            emit_assets=emit_assets,
        )
        for child in node.children
    ).strip()

    component_id = node.attrs.get("id")
    if not component_id:
        if not renderer._auto_id:
            raise ValueError(
                f'Missing required "id" for <{node.name}> and auto_id=False'
            )
        component_id = f"{node.name.lower()}-{uuid.uuid4().hex}"

    attrs_without_id = {k: v for k, v in node.attrs.items() if k != "id"}

    registry_key = Registry.make_key(node.name, component_id)
    existing_instance = Registry.get_instances().get(registry_key)
    template_path: str | None = None
    try:
        template_path = renderer._find_template_for_tag(node.name)
    except FileNotFoundError:
        pass

    if existing_instance is not None:
        instance_class_name = type(existing_instance).__name__
        if instance_class_name != node.name:
            raise TypeError(
                f"Tag <{node.name}> references instance '{component_id}' "
                f"which is of type {instance_class_name}"
            )

        updates: dict[str, Any] = dict(attrs_without_id)
        if rendered_children:
            updates["content"] = rendered_children
        existing_instance = existing_instance.model_copy(update=updates)
        Registry.get_instances()[registry_key] = existing_instance

        return str(
            existing_instance._render(
                base_context=base_context,
                _renderer=renderer,
                _session=session,
                _template_path=template_path,
                emit_assets=emit_assets,
            )
        )

    if not Registry.has_class(node.name):
        ComponentAutodiscover.try_for_tag(node.name, template_path)

    component_class = Registry.get_class(node.name)
    if component_class is not None:
        component = component_class(
            id=component_id,
            content=rendered_children,
            **attrs_without_id,
        )
    else:
        if template_path is None:
            raise FileNotFoundError(
                f"No template found for <{node.name}>. "
                f"Expected {node.name.lower()}.html or {node.name.lower()}.jinja"
            )
        from .base import BaseComponent

        component = BaseComponent(
            id=component_id,
            content=rendered_children,
            **attrs_without_id,
        )
        Registry.get_instances().pop(
            Registry.make_key("BaseComponent", component_id), None
        )

    return str(
        component._render(
            base_context=base_context,
            _renderer=renderer,
            _session=session,
            _template_path=template_path,
            emit_assets=emit_assets,
        )
    )


def expand_custom_tags(
    renderer: Renderer,
    markup: str,
    base_context: dict[str, Any],
    session: RenderSession,
    *,
    emit_assets: bool,
) -> str:
    """Expand PascalCase custom tags found inside ``markup``."""
    if "<" not in markup:
        return markup

    parser = Parser()
    has_custom_tags = False
    for match in re.finditer(r"<\s*([A-Za-z][A-Za-z0-9]*)", markup):
        if parser._is_custom_component(match.group(1)):
            has_custom_tags = True
            break
    if not has_custom_tags:
        return markup

    parser.feed(markup)
    parser.close()
    return "".join(
        render_tag_node(
            renderer,
            node,
            base_context=base_context,
            session=session,
            emit_assets=emit_assets,
        )
        for node in parser.root_nodes
    )
