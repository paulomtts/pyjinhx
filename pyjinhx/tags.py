"""Tag data model, HTML-like parser, autodiscovery, and PascalCase tag expansion."""

from __future__ import annotations

import importlib.util
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any, ClassVar

from markupsafe import escape

from .registry import Registry
from .utils import (
    extract_tag_name_from_raw,
    pascal_case_to_snake_case,
    tag_name_to_template_filenames,
)

logger = logging.getLogger("pyjinhx")


@dataclass
class Tag:
    """
    Represents a parsed HTML/component tag with its attributes and children.

    Used by the Parser to build a tree structure from HTML-like markup containing
    PascalCase component tags (e.g., `<MyButton text="OK">`).

    Attributes:
        name: The tag name (e.g., "MyButton", "div").
        attrs: Dictionary of attribute names to values.
        children: Nested tags or raw text content within this tag.
    """

    name: str
    attrs: dict[str, str]
    children: list["Tag | str"] = field(default_factory=list)


RE_PASCAL_CASE_TAG_NAME = re.compile(r"^[A-Z](?=[A-Za-z0-9]*[a-z])[A-Za-z0-9]*$")


class Parser(HTMLParser):
    """
    HTML parser that identifies PascalCase component tags and builds a tree of Tag nodes.

    Standard HTML tags are passed through as raw strings, while PascalCase tags (e.g., `<MyButton>`)
    are parsed into Tag objects for component rendering. After calling `feed(html)`, the parsed
    structure is available in `root_nodes`.

    Attributes:
        root_nodes: List of top-level parsed nodes (Tag objects or raw HTML strings).
    """

    def __init__(self) -> None:
        super().__init__()
        self._stack: list[Tag] = []
        self.root_nodes: list[Tag | str] = []

    def _is_custom_component(self, tag_name: str) -> bool:
        return bool(RE_PASCAL_CASE_TAG_NAME.match(tag_name))

    def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {attr_name: (attr_value or "") for attr_name, attr_value in attrs}

    def _append_child(self, node: Tag | str) -> None:
        if self._stack:
            self._stack[-1].children.append(node)
        else:
            self.root_nodes.append(node)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}>"
        original_tag_name = extract_tag_name_from_raw(raw) or tag

        if self._is_custom_component(original_tag_name):
            tag_node = Tag(name=original_tag_name, attrs=self._attrs_to_dict(attrs))
            self._stack.append(tag_node)
            return

        self._append_child(raw)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag} />"
        original_tag_name = extract_tag_name_from_raw(raw) or tag

        if self._is_custom_component(original_tag_name):
            tag_node = Tag(name=original_tag_name, attrs=self._attrs_to_dict(attrs))
            self._append_child(tag_node)
            return

        self._append_child(raw)

    def handle_endtag(self, tag: str) -> None:
        if self._stack and self._stack[-1].name.lower() == tag.lower():
            tag_node = self._stack.pop()
            self._append_child(tag_node)
            return

        # Plain HTML tags are never stacked, so their closing tags land here.
        if any(t.name.lower() == tag.lower() for t in self._stack):
            logger.warning(
                "Closing tag </%s> interleaves with an open component tag; "
                "emitting as raw HTML", tag,
            )
        self._append_child(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        # Re-escape decoded text so autoescaped scalars stay escaped through the
        # tag-expansion round-trip (e.g. &lt;script&gt; → decoded <script> →
        # &lt;script&gt;). Slot tags/attributes go through get_starttag_text()
        # (raw), not here, so HTML structure is preserved untouched (#120).
        #
        # Exception: <script>/<style> are raw-text (CDATA) elements. HTMLParser
        # delivers their bodies here verbatim (entities are NOT decoded), so
        # escaping would corrupt the JS/CSS — `"` → `&#34;`, `&&` → `&amp;&amp;`
        # (#177). `cdata_elem` is the open raw-text element while inside one, and
        # None otherwise, so append those bodies untouched.
        if self.cdata_elem in self.CDATA_CONTENT_ELEMENTS:
            self._append_child(data)
        else:
            self._append_child(str(escape(data)))

    def handle_comment(self, data: str) -> None:
        self._append_child(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._append_child(f"<!{decl}>")

    def close(self) -> None:
        if self._stack:
            unclosed = ", ".join(tag.name for tag in self._stack)
            raise ValueError(f"Unclosed PascalCase component tags: {unclosed}")
        super().close()


class ComponentAutodiscover:
    """Import co-located Python modules to register ``BaseComponent`` subclasses."""

    _imported_files: ClassVar[set[str]] = set()

    @classmethod
    def clear(cls) -> None:
        """Drop the deduplication sets. Mainly for tests."""
        cls._imported_files.clear()
        _warned_unregistered_tags.clear()

    @classmethod
    def import_from_file(cls, filepath: str) -> None:
        """Import a Python file by path to trigger ``BaseComponent`` registration."""
        if filepath in cls._imported_files:
            return
        cls._imported_files.add(filepath)
        try:
            module_name = (
                f"_pyjinhx_autodiscovered_{os.path.splitext(os.path.basename(filepath))[0]}"
            )
            spec = importlib.util.spec_from_file_location(module_name, filepath)
            if spec is None or spec.loader is None:
                return
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = (
                module  # required for inspect.getfile to resolve the class
            )
            spec.loader.exec_module(module)
        except Exception:
            logger.warning(
                "Autodiscovery import failed for %s; the tag will fall back to "
                "BaseComponent and class defaults will not apply.",
                filepath,
                exc_info=True,
            )

    @classmethod
    def try_for_tag(cls, tag_name: str, template_path: str | None) -> None:
        """
        Look for a co-located Python module next to the template and import it.

        Search order: ``<snake_name>.py`` → ``__init__.py`` → first alphabetical ``.py``.
        """
        if template_path is None:
            return
        component_dir = os.path.dirname(template_path)
        snake_name = pascal_case_to_snake_case(tag_name)
        for filename in (f"{snake_name}.py", "__init__.py"):
            candidate = os.path.join(component_dir, filename)
            if os.path.exists(candidate):
                cls.import_from_file(candidate)
                return
        try:
            py_files = sorted(f for f in os.listdir(component_dir) if f.endswith(".py"))
            if py_files:
                cls.import_from_file(os.path.join(component_dir, py_files[0]))
        except OSError:
            pass


if TYPE_CHECKING:
    from .assets import RenderSession
    from .renderer import Renderer


_warned_unregistered_tags: set[str] = set()

# Kept in sync with pyjinhx.builtins.__all__ by a test. Listed here instead of
# imported so the error path doesn't register every builtin as a side effect.
_BUILTIN_TAG_NAMES = frozenset(
    {
        "PJXAccordion",
        "PJXAccordionContent",
        "PJXAccordionGroup",
        "PJXAccordionTrigger",
        "PJXAlert",
        "PJXButton",
        "PJXAvatar",
        "PJXAvatarStack",
        "PJXBadge",
        "PJXBreadcrumb",
        "PJXCard",
        "PJXCardBody",
        "PJXCardFooter",
        "PJXCardHeader",
        "PJXChipInput",
        "PJXConfirmDialog",
        "PJXDivider",
        "PJXDropdown",
        "PJXDrawer",
        "PJXDrawerBody",
        "PJXDrawerFooter",
        "PJXDrawerHeader",
        "PJXEmptyState",
        "PJXFormField",
        "PJXIcon",
        "PJXLazyLoad",
        "PJXModal",
        "PJXModalBody",
        "PJXModalFooter",
        "PJXModalHeader",
        "PJXNotification",
        "PJXPageLoader",
        "PJXPopover",
        "PJXPopoverPanel",
        "PJXPopoverTrigger",
        "PJXProgress",
        "PJXPromptDialog",
        "PJXRegionLoader",
        "PJXResizableHandle",
        "PJXResizablePanel",
        "PJXResizableGroup",
        "PJXSegmentedControl",
        "PJXPasswordInput",
        "PJXSkeleton",
        "PJXSpinner",
        "PJXTable",
        "PJXTableHead",
        "PJXTableBody",
        "PJXTableRow",
        "PJXTableHeaderCell",
        "PJXTableCell",
        "PJXTab",
        "PJXTabGroup",
        "PJXTabList",
        "PJXTabPanel",
        "PJXToastHost",
        "PJXToggleSwitch",
        "PJXTooltip",
        "PJXTooltipContent",
        "PJXTooltipTrigger",
        "PJXPaginator",
    }
)


def _ambiguous_children_error(tag_name: str, component_class: type) -> ValueError:
    from .base import PjxSlot

    slots = [
        name
        for name, field in component_class.model_fields.items()
        if any(isinstance(m, PjxSlot) for m in field.metadata)
    ]
    return ValueError(
        f"<{tag_name}> has multiple slot fields ({', '.join(slots)}) and no "
        f"'content' field, so the target for nested children is ambiguous. "
        f"Mark the intended field with PjxSlot(children=True) (or the Children "
        f"alias)."
    )


def _missing_template_error(tag_name: str) -> FileNotFoundError:
    if tag_name in _BUILTIN_TAG_NAMES:
        return FileNotFoundError(
            f"<{tag_name}> is a pyjinhx builtin but its class isn't registered. "
            f"Add `from pyjinhx.builtins import {tag_name}` "
            f"(or `import pyjinhx.builtins`) once at app startup so the tag resolves."
        )
    candidates = ", ".join(tag_name_to_template_filenames(tag_name))
    return FileNotFoundError(
        f"No template found for <{tag_name}>. Expected one of: {candidates}"
    )


def _mount_reactive_instance(
    component_class: type,
    attrs_without_id: dict[str, Any],
    *,
    explicit_id: str | None,
    rendered_children: str,
    session: RenderSession,
    tag_name: str,
) -> Any:
    """Build a reactive instance for a tag mount by running ``load()``.

    The keyed id (``f"{kebab}-{key}"``) is produced by ``LoadCache`` inside
    ``load()``; an explicit ``id`` attr overrides it.
    """
    keyed = getattr(component_class, "_pjx_keyed", False)
    load_field = getattr(component_class, "_pjx_load_field", None)

    if keyed:
        if load_field is None or load_field not in attrs_without_id:
            raise ValueError(
                f"<{tag_name}> is instance-keyed; mounting it as a tag requires "
                f"the key attr '{load_field}=...'."
            )
        instance = component_class.load(attrs_without_id[load_field])
    else:
        instance = component_class.load()

    if explicit_id:
        instance.id = explicit_id

    overrides = {
        field_name: value
        for field_name, value in attrs_without_id.items()
        if field_name != load_field
    }
    children_field = component_class._pjx_children_target
    if rendered_children:
        if children_field is None:
            raise _ambiguous_children_error(tag_name, component_class)
        overrides[children_field] = rendered_children
    if overrides:
        instance = instance.model_copy()
        validator = component_class.__pydantic_validator__
        for field_name, value in overrides.items():
            validator.validate_assignment(instance, field_name, value)

    Registry.get_instances()[
        Registry.make_key(tag_name, instance.id)
    ] = instance
    return instance


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

    explicit_id = node.attrs.get("id")
    attrs_without_id = {k: v for k, v in node.attrs.items() if k != "id"}

    template_path: str | None = None
    try:
        template_path = renderer._find_template_for_tag(node.name)
    except FileNotFoundError:
        pass

    # Resolve the class up front so we can tell a reactive tag from a plain one
    # before assigning its id. Autodiscovery and {#def#} model-building are
    # idempotent and deduplicated, so running them here is safe.
    if not Registry.has_class(node.name):
        ComponentAutodiscover.try_for_tag(node.name, template_path)
    if not Registry.has_class(node.name) and template_path is not None:
        from .props_header import build_component_model

        with open(template_path, encoding="utf-8") as template_file:
            build_component_model(node.name, template_file.read())

    component_class = Registry.get_class(node.name)

    from .reactive import ReactiveComponent

    is_reactive = component_class is not None and issubclass(
        component_class, ReactiveComponent
    )

    # A reactive tag derives its id from load() (or an explicit id attr), never a
    # random auto_id. Non-reactive tags keep the existing id rules.
    if explicit_id:
        component_id: str | None = explicit_id
    elif is_reactive:
        component_id = None
    elif renderer._auto_id:
        from .base import _auto_id

        component_id = _auto_id()
    else:
        raise ValueError(
            f'Missing required "id" for <{node.name}> and auto_id=False'
        )

    # Reuse an already-registered instance when we have a concrete id to look up.
    # Bare reactive tags skip this and go straight to load(), whose LoadCache
    # already dedupes per request.
    if component_id is not None:
        registry_key = Registry.make_key(node.name, component_id)
        existing_instance = Registry.get_instances().get(registry_key)
        if existing_instance is not None:
            instance_class_name = type(existing_instance).__name__
            if instance_class_name != node.name:
                raise TypeError(
                    f"Tag <{node.name}> references instance '{component_id}' "
                    f"which is of type {instance_class_name}"
                )

            updates: dict[str, Any] = dict(attrs_without_id)
            if rendered_children:
                target = type(existing_instance)._pjx_children_target
                if target is None:
                    raise _ambiguous_children_error(node.name, type(existing_instance))
                updates[target] = rendered_children
            if updates:
                updated_instance = existing_instance.model_copy()
                validator = type(existing_instance).__pydantic_validator__
                for field_name, field_value in updates.items():
                    validator.validate_assignment(
                        updated_instance, field_name, field_value
                    )
                existing_instance = updated_instance
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

    if is_reactive:
        component = _mount_reactive_instance(
            component_class,
            attrs_without_id,
            explicit_id=explicit_id,
            rendered_children=rendered_children,
            session=session,
            tag_name=node.name,
        )
    elif component_class is not None:
        init_kwargs: dict[str, Any] = dict(attrs_without_id)
        children_field = component_class._pjx_children_target
        if rendered_children and children_field is None:
            raise _ambiguous_children_error(node.name, component_class)
        if children_field is not None:
            if rendered_children and children_field in init_kwargs:
                raise ValueError(
                    f"<{node.name}> received both children and the "
                    f"'{children_field}' attribute; supply one"
                )
            if rendered_children or children_field not in init_kwargs:
                init_kwargs[children_field] = rendered_children
        component = component_class(id=component_id, **init_kwargs)
    else:
        if template_path is None:
            raise _missing_template_error(node.name)
        from .base import BaseComponent

        component_dir = os.path.dirname(template_path)
        snake_name = pascal_case_to_snake_case(node.name)
        sibling_py = os.path.join(component_dir, f"{snake_name}.py")
        if os.path.exists(sibling_py) and node.name not in _warned_unregistered_tags:
            _warned_unregistered_tags.add(node.name)
            logger.warning(
                "Template found for <%s> but class %s is not registered — "
                "defaults won't apply. Import the module defining %s at app startup.",
                node.name, node.name, node.name,
            )

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
