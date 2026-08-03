"""L0.4.4/L0.4.6 render — single-level pipeline and public API.

Descriptor read → context build → Jinja render → single parse → RenderedLevel
(render_level, internal). serialize(render_level(...)) closes the loop into a
finished HTML string for a childless component (render, public API).
"""

import html
from typing import cast

import jinja2
from pydantic import TypeAdapter

from pyjinhx.assets import emit_assets
from pyjinhx.component import BaseComponent, _pascal_to_snake
from pyjinhx.discovery import get_class
from pyjinhx.markers import SLOT_TOKEN_RE, collect_slot_tokens
from pyjinhx.props_header import warn_stale_def_header
from pyjinhx.render_context import build_context
from pyjinhx.segments import ChildRef, RenderedLevel, VerbatimParser, serialize
from pyjinhx.session import RenderSession

# How many times one class may appear on a single nesting path before the path
# is treated as a cycle. A terminating design reuses a class a handful of times
# at most; a component that re-instantiates itself with no base case blows past
# this, and does so well inside Python's recursion limit.
MAX_CHAIN_REPEATS = 32


def _passthrough_markup(ref: ChildRef) -> str:
    """Markup for a ChildRef whose tag no component class claims.

    An unregistered PascalCase tag is ordinary markup — a web component, or a
    tag someone meant to ship as-is — so it goes back into the stream instead of
    raising (architecture-overview: a registry miss is an answer, not an error).

    Reconstructed from the ChildRef's own fields, not echoed: the parse that
    produced it kept the tag, the attrs and the inner text, and dropped the raw
    source, so the original quoting style and spacing are not recoverable here.
    ``inner`` was captured verbatim and is emitted raw; attr values are
    re-escaped because they arrive from the parse already unescaped.
    """
    attrs = "".join(
        f' {name}="{html.escape(value, quote=True)}"'
        for name, value in ref.attrs.items()
    )
    if ref.inner is None:
        return f"<{ref.tag}{attrs}/>"
    return f"<{ref.tag}{attrs}>{ref.inner}</{ref.tag}>"


def _child_kwargs(ref: ChildRef, cls: type[BaseComponent]) -> dict[str, str]:
    """Attr/body-text kwargs a resolved ChildRef contributes to its child.

    A paired tag's ``inner`` is merged raw, not parsed: it becomes a field value
    that the child's own template re-emits, so the tags inside it are cut out by
    the child's own parse and this level still parses exactly once.

    Raises:
        ValueError: The tag carries body text but the class names no children
            field, or the same field also arrived as an explicit attribute.
    """
    kwargs: dict[str, str] = dict(ref.attrs)
    if ref.inner is not None and ref.inner.strip():
        field = cls.__pjx_descriptor__.children_field
        if field is None:
            raise ValueError(
                f"<{ref.tag}> was given body text, but {cls.__name__} names no "
                f"children field; mark one field Children or write the tag "
                f"self-closing."
            )
        if field in kwargs:
            raise ValueError(
                f"<{ref.tag}> received both body text and a {field!r} attribute; "
                f"supply one."
            )
        kwargs[field] = ref.inner
    return kwargs


def _instantiate_child(ref: ChildRef, cls: type[BaseComponent]) -> BaseComponent:
    """Construct ``cls`` from a resolved ChildRef's attrs and body text.

    Construction is the whole coercion step: the class's own validators turn
    JSON-looking attr strings into lists/dicts/models and fill an omitted id, so
    nothing here re-implements them and their errors reach the caller unchanged.
    """
    return cls(**_child_kwargs(ref, cls))


# Sentinel for the reactive duck-type: ReactiveComponent sets _pjx_key_field on
# every subclass at __pydantic_init_subclass__ time and nothing else in the tree
# defines it, so its mere presence identifies a reactive class without rendering
# .py importing reactive/ (a plain component's value is never None — the
# attribute is simply absent).
_NO_KEY_FIELD = object()


def _load_reactive_child(
    ref: ChildRef, cls: type[BaseComponent], key_field: str | None
) -> BaseComponent:
    """Build a reactive child by calling its ``load()`` factory, then apply attrs.

    ``load()`` owns construction, so the key attr goes in as its argument and
    everything else is assigned onto whatever instance comes back — which, on a
    repeat key inside one request, is the very instance an earlier tag already
    got, cache hit and all.

    ``validate_assignment`` only runs field-level validation, not the model's
    ``mode="before"`` validators — a raw JSON-looking string assigned to a
    ``list``/``dict``/``BaseModel`` field raises ``list_type`` instead of being
    parsed. So the same JSON-string coercion ``_instantiate_child`` gets for
    free from construction has to be run explicitly here, via the class's own
    ``_coerce_json_string_attrs`` (the single source of truth for that
    coercion, not a second implementation of it), before each field is
    assigned and type-validated.
    """
    kwargs = _child_kwargs(ref, cls)
    key_args: dict[str, object] = {}
    if key_field is not None and key_field in kwargs:
        raw_key = kwargs.pop(key_field)
        # A tag attr always arrives as a string (Jinja renders the tag before
        # it's parsed); load() is a plain method, not a pydantic constructor,
        # so nothing coerces it on the way in unless this does.
        annotation = cls.model_fields[key_field].annotation
        key_args[key_field] = TypeAdapter(annotation).validate_python(raw_key)
    instance = cast(BaseComponent, cls.load(**key_args))  # pyright: ignore[reportAttributeAccessIssue]
    coerced = cls._coerce_json_string_attrs(kwargs)  # pyright: ignore[reportAttributeAccessIssue]
    for name, value in cast(dict[str, object], coerced).items():
        cls.__pydantic_validator__.validate_assignment(instance, name, value)
    return instance


def _fill_children(level: RenderedLevel) -> list[tuple[int, BaseComponent]]:
    """Resolve each ChildRef in ``level`` against the class registry, in place.

    Tags no class claims stop being holes here and go back to being markup.
    Tags that do resolve are built once, in document order — a reactive class
    through its cache-routed ``load()`` factory, a plain one through its
    constructor — and returned with their segment index so the recursive step
    can render each one and splice it back where its ChildRef still sits.
    """
    pending: list[tuple[int, BaseComponent]] = []
    for index, segment in enumerate(level.segments):
        if not isinstance(segment, ChildRef):
            continue
        cls = get_class(_pascal_to_snake(segment.tag))
        if cls is None:
            level.segments[index] = _passthrough_markup(segment)
            continue
        cls = cast(type[BaseComponent], cls)
        key_field = getattr(cls, "_pjx_key_field", _NO_KEY_FIELD)
        if key_field is _NO_KEY_FIELD:
            child = _instantiate_child(segment, cls)
        else:
            child = _load_reactive_child(segment, cls, cast("str | None", key_field))
        pending.append((index, child))
    return pending


def _splice_slot_nodes(
    level: RenderedLevel,
    table: dict[str, BaseComponent],
    session: "RenderSession",
    chain: tuple[str, ...],
) -> None:
    """Replace each slot placeholder token in ``level`` with the child's RenderedLevel.

    The tokens were emitted by the finalize hook during this level's template
    render and came through the level's single parse as ordinary character data,
    so resolving them is string splitting over segments already cut — never a
    second parse (ADR 0005). Each token's component is rendered here and nowhere
    else, which is what keeps truthiness and context building render-free.

    Raises:
        ValueError: If a token lands inside a tag's raw text (a slot
            interpolated into an attribute), or if a token appears more than
            once in the output.
    """
    if not table:
        return
    seen: dict[str, int] = {}
    spliced: list[str | ChildRef | RenderedLevel] = []
    for segment in level.segments:
        if not isinstance(segment, str) or "pjx-slot-" not in segment:
            spliced.append(segment)
            continue
        if segment.startswith("<"):
            raise ValueError(
                "a component-valued slot was interpolated inside a tag "
                f"({segment!r}); slots may only be interpolated as element content."
            )
        position = 0
        for match in SLOT_TOKEN_RE.finditer(segment):
            token = match.group(0)
            child = table.get(token)
            if child is None:
                continue
            seen[token] = seen.get(token, 0) + 1
            if seen[token] > 1:
                raise ValueError(
                    f"slot placeholder {token} appears more than once in the "
                    "rendered output; the token collided with literal text."
                )
            head = segment[position : match.start()]
            if head:
                spliced.append(head)
            # Each child gets its own render_level call, so it does its own
            # single parse and enters segments as a whole object.
            spliced.append(render_level(child, session, chain))
            position = match.end()
        tail = segment[position:]
        if tail:
            spliced.append(tail)
    level.segments = spliced


def render_level(
    component: BaseComponent,
    session: "RenderSession",
    chain: tuple[str, ...] = (),
) -> RenderedLevel:
    """Render one component level: template → one parse → RenderedLevel.

    Args:
        component: A valid BaseComponent instance (construction-time validation passed).
        session: RenderSession providing Jinja environment and hooks.
        chain: Class names of the components already being rendered on this
            call path, outermost first, one entry per level (a class may appear
            more than once). Passed by value down the recursion so each branch
            sees its own ancestors and nothing else.

    Returns:
        RenderedLevel with segments (str | ChildRef), root_span, descriptor.

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        ValueError: If one class recurs MAX_CHAIN_REPEATS times on a single
            call path — a path that has stopped making progress. Reusing a
            class at a shallower and a deeper level of the same path is not a
            cycle and does not raise.
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
        Exception: Whatever a session.on_rendered subscriber raises; the hook
            does not isolate subscribers from the render.
    """
    # Phase 1: Descriptor read
    descriptor = component.__class__.__pjx_descriptor__

    # One attribute read on the hot path; the probe that answered it ran once,
    # when the class was registered.
    if descriptor.has_stale_def_header:
        warn_stale_def_header(component.__class__)

    # Phase 2: Context build — component-valued slots arrive as ComponentNode,
    # string-valued slots arrive as Markup so authored markup survives
    # autoescape.
    context = build_context(component, descriptor)

    # Phase 3: Jinja render with autoescape ON
    jinja_env = session.jinja_env
    prefix = f"{component.__class__.__name__} (template: {descriptor.template_path}): "

    # A class may legitimately reappear deeper on the same path — Card > Row >
    # Card terminates — so mere presence in the chain proves nothing. What a
    # real cycle looks like is a path that stops making progress: the same class
    # recurring over and over. The chain is the current call path only, so the
    # same class on two sibling branches is still fine (ADR 0004: nesting/load
    # chains are the only cycle vector left in v2).
    name = component.__class__.__name__
    if chain.count(name) >= MAX_CHAIN_REPEATS:
        # `chain` is a tuple (no .rindex()); walk from the end to find the most
        # recent occurrence, so the message names one turn of the loop rather
        # than every repetition of it.
        last = len(chain) - 1 - chain[::-1].index(name)
        cycle = chain[last:]
        raise ValueError(f"{prefix}cycle detected: {' -> '.join((*cycle, name))}")
    chain = (*chain, name)

    try:
        template = jinja_env.get_template(str(descriptor.template_path))
    except jinja2.TemplateNotFound as err:
        raise jinja2.TemplateNotFound(
            err.name, message=f"{prefix}template file not found"
        ) from err
    with collect_slot_tokens() as slot_table:
        output_string = template.render(context)

    # Phase 4: Single parse via VerbatimParser
    parser = VerbatimParser()
    parser.feed(output_string)
    parser.close()

    # Validate single-root rule
    try:
        parser.enforce_single_root()
    except ValueError as err:
        raise ValueError(f"{prefix}{err}") from err

    # Return RenderedLevel
    level = RenderedLevel(
        segments=cast(list[str | ChildRef | RenderedLevel], parser.segments),
        root_span=parser.root_span or (0, 0),
        descriptor=descriptor,
    )
    # Unregistered tags stop being holes here, one pass per level (ADR 0005);
    # the ones that do resolve arrive already built — a reactive child through
    # its cache-routed load() factory, a plain one through its constructor.
    for index, child in _fill_children(level):
        # Each child gets its own render_level call, so it does its own single
        # parse and enters this list as a whole object — never text spliced into
        # text, which is what keeps a child's markup un-reparsed and un-escaped.
        level.segments[index] = render_level(child, session, chain)
    # Runs after tag-shaped holes are resolved, so the indexes above stay valid
    # while this step rebuilds the list.
    _splice_slot_nodes(level, slot_table, session, chain)
    # Last statement on purpose: children and slots already fired their own hooks
    # from their own render_level calls, so subscribers see a finished subtree and
    # session state accumulates bottom-up. Fired for every component, subscribers
    # or not — an empty list is the zero-cost case, not a branch to skip.
    session.emit_rendered(component, level)
    return level


def render(component: BaseComponent, session: "RenderSession | None" = None) -> str:
    """Render a component to a final HTML string (public API).

    Thin wrapper closing the loop for a childless component: render_level()
    produces one component's RenderedLevel, serialize() joins its segments
    back into markup. Internal/recursive callers (L1) call render_level()
    directly instead, since they need the RenderedLevel, not a string.

    Args:
        component: A valid BaseComponent instance.
        session: RenderSession providing the Jinja environment. Defaults to
            a fresh RenderSession() when omitted, so callers outside the
            kernel don't need to construct one by hand.

    Returns:
        The component's rendered markup as a finished HTML string, with the
        session's accumulated assets appended per their delivery mode.

    Fires each ``session.on_rendered`` callback with ``(component, level,
    session)`` after each component's level is built, depth-first post-order.
    ``session`` is always the one passed to (or defaulted inside) this call,
    never read off any ContextVar, so hooks work whether or not ``session``
    is also the active request_scope().

    Raises:
        ValueError: If template renders zero or 2+ root elements.
        jinja2.TemplateNotFound: If template file missing.
        jinja2.TemplateAssertionError: If Jinja evaluation fails.
        AssertionError: If a segment reaching serialize() is neither str
            nor RenderedLevel (unresolved ChildRef reaching the boundary).
    """
    if session is None:
        session = RenderSession()
    level = render_level(component, session)
    # The one join at the top, and the one place assets are emitted: every
    # component in the tree has already fired on_rendered by now, so the
    # session's asset sets are complete. render_level() never lands here.
    return serialize(level) + emit_assets(session)
